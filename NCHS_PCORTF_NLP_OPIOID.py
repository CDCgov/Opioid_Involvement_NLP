"""
Python 3.7
Code for PCORTF FY18 project on National Hopsital Care Survey
Designed to flag opioids and opioid overdoses

updated 11/23/21
@author: Nikki Adams oxf7@cdc.gov
"""
import configparser
import csv
import logging
from pathlib import Path
import re
import sys
#below used in case to import from paths not in default sys.path
#code_dir = Path(r'\\mypathhere')
#if str(code_dir) not in sys.path:
#    sys.path.append(str(code_dir))


from negex_adjusted import negTagger, sortRules
#similarity scores used for spelling suggestion, not implemented in this release
#from nltk.metrics.distance import jaro_similarity, edit_distance
from nltk.tokenize import sent_tokenize

from build_queries import Query


def eval_inclusion(sentence, target, negrules, NER_model, date_exclusion_regex):
    #is it negated? if there's a date exclusion, is it excluded by date?
    included = False
    tagger = negTagger(sentence = sentence, phrases = [target], rules = negrules, negP=False)
    if tagger.getNegationFlag()=="affirmed":
        included = True
    #HERE TEST CODE FOR MORE DIRECT DATE DETECTION IN LABELS and put in better date exclusion
        if date_exclusion_regex:
            doc = NER_model(sentence)
            for ent in doc.ents:
                if ent.label_ == "DATE" and re.search(date_exclusion_regex, ent.text):
                    included = False
                    break
    return(included)

def search_overdose(orig_note, opioid_regex, negrules, NER_model, date_exclusion, exclusion_regex):

    #sentences is list of length 3. target non-negated drug has already been found in sentences[1]
    overdose_regex = re.compile(r'poison|overd[ou]se', flags=re.IGNORECASE)
    if re.search(overdose_regex, orig_note) is None or re.search(opioid_regex, orig_note) is None:
        return(0)
    #no need to do a sentence-by-sentence search
    
    
    #first get rid of spurious 'sentences'. if nothing left after that, return False
    orig_sents = [x for x in sent_tokenize(orig_note) if len(x.strip())> 2]
    if orig_sents ==[]:
        return(0)
    #now for easier processing prepend and append a final empty string sent
    orig_sents.insert(0,'')
    orig_sents.append('')
    for i in range(1, len(orig_sents)-1):
        previous_sent = orig_sents[i-1]
        current_sent = orig_sents[i]
        following_sent = orig_sents[i+1]

        #overdose keywords?
        m = re.search(overdose_regex, current_sent)
        if not m:
            continue
        #overdose keywords excluded? if the overdose trigger itself is excluded, continue
        od_included = eval_inclusion(current_sent, m.group(), negrules, NER_model, date_exclusion)
        if not od_included:
            continue
           
        #if the overdose trigger in current sentence is not excluded, 
        #evaluate for co-occurrence of the drug terms

        primary_terms = re.findall(opioid_regex, current_sent)
        for term in set(primary_terms):
            if not(eval_inclusion(current_sent, term, negrules, NER_model, date_exclusion)):
                continue
#            od_drug = term #We don't do anything with this, but could
            return(1)
        #if no opioid terms in current sentence co-occurring with od term, look for other drugs 
        #if other drug co-occurs, no primary term OD for this current sentence           
        exclusion_terms = re.findall(exclusion_regex, current_sent)
        other_drug_od = False
        for term in set(exclusion_terms):
            if eval_inclusion(current_sent, term, negrules, NER_model, date_exclusion):
                other_drug_od = True
        if other_drug_od:
            continue
 
        #if no drugs found so far, search for primary terms in previous and following sentences
        #if found and not included, return True for this note for primary term overdose
        previous_sent_matches = re.findall(opioid_regex, previous_sent)
        for term in set(previous_sent_matches):
            if eval_inclusion(current_sent, term, negrules, NER_model, date_exclusion):
                return(1)


        following_sent_matches = re.findall(opioid_regex, following_sent)
        for term in set(following_sent_matches):
            if eval_inclusion(current_sent, term, negrules, NER_model, date_exclusion):
                return(1)
                
    #if you go through all sentences without returning True, return False                  
    return(0)
    

def search_plain_text(orig_note, opioid_regex, negrules, NER_model, date_exclusion):
    #search_plain_text(note_text, search_terms_regex, negrules)
    #for speed, search for opioids, other drugs, NER and if no drug matches at
    #all, don't do more careful search. 6/16 update, i do this upfront in a separate process
    #at this point, everything looked at should have some type of drug
    
    #if there were any drugs found, go ahead and sentence tokenize
    
#    sentences = [x for x in sent_tokenize(orig_note) if len(x)>2] #get rid of single char and punc "sentences"
    #exclusions are done sentence by sentence. check for date exclusions, check for date
    #exclusions, if novel drug ner candidate, try to map it to correct spelling of opioid
    all_confirmed_matches = set() #members are strings
    #consider adding back in just for date using base spaCy NER model
    if date_exclusion:
        sentences = []
        for sentence in [x for x in sent_tokenize(orig_note) if len(x)>2]:
            #right now, no scope restriction for date exclusion except within sentence,
            #so might as well do it up front. might refine later 
            date_excluded = False
            doc = NER_model(sentence)
            for ent in doc.ents:
                if ent.label_ == "DATE" and re.search(date_exclusion, ent.text):
                    continue
                    date_excluded = True
                    break     
            if date_excluded:
                continue
            sentences.append(sentence)
    else:
        sentences = [x for x in sent_tokenize(orig_note) if len(x)>2]
        
    for sent_position, sentence in enumerate(sentences):
        regex_matches = set([x.lower() for x in re.findall(opioid_regex, sentence)])              
       
        for match in regex_matches:
            tagger = negTagger(sentence, [match], negrules, negP=False)
            if tagger.getNegationFlag()=="negated":
                continue
            all_confirmed_matches.add(match.lower())

    return(all_confirmed_matches)


def build_category_map(mapping_file):
    with mapping_file.open(encoding='utf-8') as INFILE:
        lines = INFILE.read().splitlines()
        term_to_category_dictionary = {}
        for counter, line in enumerate(lines):
            line = line.lower().strip()
            if line=='':
                continue
            if "term" in line or "category" in line and counter==0:
                continue
            term, category = [x.strip() for x in line.split(",")]
            term_to_category_dictionary[term] = category        
    return(term_to_category_dictionary)

def build_regex(query_path, search_type = "boundary with s"):
    query = Query(query_path)
    regex = query.build_re(search_type)         
    return (regex)


def main_search(input_args):
    input_type, cnxn_string, cursor_execute_string, csv_input_file, search_terms_path, \
    negex_triggers_path, results_file, search_column, output_vars, upfront_val_exclusions, \
    val_exclusion_column, upfront_val_inclusions, val_inclusion_column, upfront_string_exclusions, NER_model, \
    date_exclusion, overdose, exclusion_drugs_path, output_zeros = input_args


    if upfront_string_exclusions:
        string_exclusion_values = r"|".join(upfront_string_exclusions)
        logging.info(f"Read in string exclusions and building regular expression as {string_exclusion_values}")
        string_exclusion_regex = re.compile(string_exclusion_values, flags = re.IGNORECASE)
    else:
        string_exclusion_values = None
        logging.info("No text exclusions specified")
    if overdose:
        exclusion_regex = build_regex(exclusion_drugs_path)
    #TODO: Let user choose how to build regex
    logging.info("Building search terms regular expressions ...")      
    search_terms_regex = build_regex(search_terms_path)
    
    logging.info("Building term to category dictionary ...")    
    term_to_category_dictionary = build_category_map(search_terms_path)
    categories = sorted(set([x[1].lower() for x in term_to_category_dictionary.items()])) #header    
    
    logging.info("Building negation rules ...")
    with negex_triggers_path.open(encoding='utf-8-sig') as RFILE:
        negrules = sortRules(RFILE.readlines())

    if input_type == "CSV":
        infile = csv_input_file
        #read and get  headers, make all upper case, and specify upper case as fieldnames, also strip whitespace
        
        with infile.open(encoding='utf-8', newline='') as csvin:
            cursor = csv.DictReader(csvin)  
            modified_fieldnames = [x.strip().upper() for x in cursor.fieldnames]
        #now open file for reading and advance one to not process first line
        csvin = infile.open(encoding='utf-8', newline='')
        cursor = csv.DictReader(csvin, fieldnames = modified_fieldnames)
        cursor.__next__()


    else:
        logging.info(f"Connecting to database with connection string {cnxn_string} and starting cursor selection ...")
        cnxn = pyodbc.connect(cnxn_string)
        cursor = cnxn.cursor()
        cursor.execute(cursor_execute_string)
        logging.info(f'Connected to database with string {cursor_execute_string}')
 
    OUTCSV = open(results_file, "w", encoding='utf-8', newline='')
    writer = csv.writer(OUTCSV)
    #linkage_vars either must assume case-insensitivity or instruct user to ensure case is correct
    if overdose:
        header = output_vars+[x.upper() for x in categories]+["OTH_TERMS_LIST", "OVERDOSE"]
    else:
        header = output_vars+[x.upper() for x in categories]+["OTH_TERMS_LIST"]
    writer.writerow(header) #header row      
    
    encounter_flags =  {x:0 for x in categories}
    od_value = 0
    for counter, row in enumerate(cursor):
        if counter%100000==0:
            logging.info(f"At row {counter} ...")
        #optional exclusions
        output_vars_vals = [row[x] for x in output_vars]

        if upfront_val_exclusions and str(row[val_exclusion_column]) in upfront_val_exclusions:
            # Hospital Discharge Instructions todo, get EHR version of this
            if output_zeros and overdose:
                row_results = output_vars_vals + [0]*len(encounter_flags) + ['', od_value]
                writer.writerow(row_results)
                continue
            if output_zeros and not overdose:
                row_results = output_vars_vals + [0]*len(encounter_flags) + ['']
                writer.writerow(row_results)
                continue                
            else:
                continue
            
        if upfront_val_inclusions and str(row[val_inclusion_column]) not in upfront_val_inclusions:
            # Hospital Discharge Instructions todo, get EHR version of this
            if output_zeros and overdose:
                row_results = output_vars_vals + [0]*len(encounter_flags) + ['', od_value]
                writer.writerow(row_results)
                continue
            if output_zeros and not overdose:
                row_results = output_vars_vals + [0]*len(encounter_flags) + ['']
                writer.writerow(row_results)
                continue                
            else:
                continue
                
        if string_exclusion_values:
            excl_m = re.search(string_exclusion_regex, row[search_column][:300])
            if excl_m is not None:
                if output_zeros and overdose:
                    row_results = output_vars_vals + [0]*len(encounter_flags) + ['', od_value]
                    writer.writerow(row_results)
                    continue
                if output_zeros and not overdose:
                    row_results = output_vars_vals + [0]*len(encounter_flags) + ['']
                    writer.writerow(row_results)
                    continue                
                else:
                    continue

        note_text = row[search_column]
        term_matches = search_plain_text(note_text, search_terms_regex, negrules, NER_model, date_exclusion)
        if overdose:
            od_value = search_overdose(note_text, search_terms_regex, negrules, NER_model, date_exclusion, exclusion_regex)     
            
        other_terms = set()                    
        for match in term_matches:
            match = match.lower()
            if match not in term_to_category_dictionary and match.endswith('s'):
                match = match[:-1]
            try:
                category = term_to_category_dictionary[match] #category is a lower case string
                encounter_flags[category] = 1
                if category == "oth_opioid":
                    other_terms.add(match)
            except Exception as e:
                print(f"Couldn't find term {match} in term to cats dictionary, with error {str(e)}")
                   
        category_values = [encounter_flags[category] for category in sorted(categories)]
        if overdose:
            row_results = output_vars_vals + category_values + [';'.join(sorted(other_terms))] + [od_value]
            if not output_zeros and max(category_values+[od_value])==0:
                continue
        else:
            if not output_zeros and max(category_values)==0:
                continue
            row_results = output_vars_vals + category_values + [';'.join(sorted(other_terms))]
        writer.writerow(row_results)
        encounter_flags =  {x:0 for x in categories}#reset
        od_value = 0 #reset
            
    logging.info(f"Finished at {counter} rows")
    OUTCSV.close()  
    if input_type == "CSV":      
        csvin.close()

 

def parse_config(configfile):
    #args needed:
    #input_type, cnxn_string, execute_string, csv_input_file
    #search_terms_path, negex_triggers_path, 
    #results_file, logging_file
    #col_to_search, output_columns

    config = configparser.ConfigParser()   
    config.read(configfile)

    #OUTPUT. Let's start here to get logfile up and running
    if "results_file" not in config['OUTPUT'] or "logging_file" not in config['OUTPUT']:
        raise KeyError("You must specify results_file path and logging_file path")
    results_file = config['OUTPUT']['results_file'].strip()
    logging_file = config['OUTPUT']['logging_file'].strip()
    if results_file == '' or logging_file == '':
        raise ValueError("You must specify results_file and logging_file")
    results_file = Path(results_file)
    logging_file = Path(logging_file)
    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s',
                        level=logging.INFO, filemode='w', filename=logging_file) 
    logging.info(f"Your output file has been specified as: {results_file.name}")
    #INPUT_SETTINGS

    if config['INPUT_SETTINGS']['input_type'].upper().strip() == "DB":
        input_type="DB"
        import pyodbc
        if ("cnxn_string" not in config['INPUT_SETTINGS']) or ("cursor_execute_string" not in config["INPUT_SETTINGS"]):
            raise KeyError("You specified input type as DB but did not specify cnxn_string or did not specify cursor_execute_string")

        cnxn_string = config['INPUT_SETTINGS']['cnxn_string'].strip()
        cursor_execute_string = config['INPUT_SETTINGS']['cursor_execute_string'].strip()
        
        if cnxn_string =='' or cursor_execute_string=="":
            raise ValueError("You have not specified cnxn_string or cursor_execute_string")
        csv_input_file = None            

    elif config['INPUT_SETTINGS']['input_type'].upper().strip() == "CSV":
        input_type="CSV"
        if "csv_input_file" not in config["INPUT_SETTINGS"]:
            raise KeyError("You specified input type as CSV but did not specify csv_input_file")
        csv_input_file = config['INPUT_SETTINGS']['csv_input_file'].strip()
        if csv_input_file=="":
            raise ValueError("You have specified input_type as CSV but did not specified csv_input_file")
        csv_input_file = Path(csv_input_file)
        cnxn_string = None
        cursor_execute_string = None
    else:
        sys.exit("You must specify input_type as DB or CSV")
    logging.info(f"Your input type has been specified as {input_type}")

    
    #TERMS
    if "search_terms_path" not in config['TERMS'] or "negex_triggers_path" not in config['TERMS']:
        raise KeyError("You must specify search_terms_path and negex_triggers_path")
    search_terms_path = config['TERMS']["search_terms_path"].strip()
    negex_triggers_path = config['TERMS']["negex_triggers_path"].strip()
    if search_terms_path =='' or negex_triggers_path=='':
        raise ValueError("You must enter paths for search_terms_path and negex_triggers_path")
    search_terms_path = Path(search_terms_path)
    negex_triggers_path = Path(negex_triggers_path)

   
    
    #SEARCH_CONFIG
    if "col_to_search" not in config['SEARCH_CONFIG']:
        raise KeyError("You must specify which column to search")
    search_column = config['SEARCH_CONFIG']['col_to_search'].strip()
    if search_column == '':
        raise ValueError("You must specify which column to search")
        
    if "output_columns" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['output_columns'].strip()=='':
        output_vars = []
    else:
        output_vars = [x.upper().strip() for x in config['SEARCH_CONFIG']['output_columns'].split(',') if x.strip()]

    if "upfront_val_exclusions" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['upfront_val_exclusions'].strip()=='':        
        upfront_val_exclusions=None
    else:
        upfront_val_excl_in = [x.strip() for x in config['SEARCH_CONFIG']['upfront_val_exclusions'].split(",") if x.strip()]
        upfront_val_exclusions = upfront_val_excl_in[1:]
        val_exclusion_column = upfront_val_excl_in[0].upper()
        

    if "upfront_val_inclusions" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['upfront_val_inclusions'].strip()=='':        
        upfront_val_inclusions=None
    else:
        upfront_val_incl_in = [x.strip() for x in config['SEARCH_CONFIG']['upfront_val_inclusions'].split(",") if x.strip()]
        upfront_val_inclusions = upfront_val_incl_in[1:]
        val_inclusion_column = upfront_val_incl_in[0].upper()

    if "upfront_string_exclusions" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']["upfront_string_exclusions"].strip()=='':
        upfront_string_exclusions=None
    else:
        upfront_string_exclusions = [x.strip() for x in config['SEARCH_CONFIG']['upfront_string_exclusions'].split(",") if x.strip()]

    if "NER_model" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['NER_model'].strip() =='':
        NER_model = None
        date_exclusion = None
        logging.info("No NER model specified and no date exclusion will be performed")
    else:
        NER_model_path = Path(config['SEARCH_CONFIG']['NER_model'].strip())
        import spacy
        NER_model = spacy.load(str(NER_model_path))
        logging.info(f"NER model successfully loaded from path {NER_model_path.name}")
        
        if "custom_date_exclusion" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['custom_date_exclusion'].strip()=='':
            custom_date_exclusion = None
        else:
            custom_date_exclusion = config['SEARCH_CONFIG']['custom_date_exclusion'].strip()
            #TODO: make sure re.escape behaves as expected
            date_exclusion = re.compile(re.escape(custom_date_exclusion)) 

        if not custom_date_exclusion:
            if "year_excluded" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['year_excluded'].strip()=='':
                raise KeyError("You specified an NER model but did not specify custom_date_exclusion or year_excluded")
            else:
                year_excluded = config['SEARCH_CONFIG']['year_excluded'].strip()
                
            if not (year_excluded.isdigit() and len(year_excluded)==4):
                raise ValueError("Year excluded must be 4 digits")     
            else:
                #date_exclusion = re.compile(r"\b2017\b|\b\d(\d)?/\d(\d)?/(20)?17\b")
                regex_string = r"\b%s\b|\b\d(\d)?/\d(\d)?/(%s)?%s\b" % (year_excluded, year_excluded[:2], year_excluded[-2:])
                date_exclusion = re.compile(regex_string)
            logging.info(f"Date exclusion: {str(date_exclusion)}")

        
    if "overdose" not in config['SEARCH_CONFIG']:
        raise KeyError("You must specify overdose as True or False")
    elif config['SEARCH_CONFIG']['overdose'].strip().lower() not in ["true", "false"]:
        raise ValueError("You must specify overdose as True or False")
    if config['SEARCH_CONFIG']['overdose'].strip().lower()=="true":
        overdose = True
    else:
        overdose = False
    if overdose and ("exclusion_drugs" not in config['SEARCH_CONFIG'] or config['SEARCH_CONFIG']['exclusion_drugs'].strip()==''):
        raise KeyError("If you set overdose to true, you must specify a path for exclusion drugs")
        
    elif overdose:
        exclusion_drugs_path = Path(config['SEARCH_CONFIG']['exclusion_drugs'].strip())
    else:
        exclusion_drugs_path = None
    
    if "output_zeros" in config['SEARCH_CONFIG'] and config['SEARCH_CONFIG']["output_zeros"].strip().lower()=="true":
        output_zeros= True
    else:
        output_zeros = False

#                
#    print(f"Val exclusion column = {val_exclusion_column}")
#    print(f"Value exclusion: {upfront_val_exclusions}")
#    print(f"Upfront_string_exclusions: {upfront_string_exclusions}")
    return([input_type, cnxn_string, cursor_execute_string, csv_input_file, search_terms_path,
            negex_triggers_path, results_file, search_column, output_vars, upfront_val_exclusions,
            val_exclusion_column, upfront_val_inclusions, val_inclusion_column, 
            upfront_string_exclusions, NER_model, 
            date_exclusion, overdose, exclusion_drugs_path, output_zeros])


def parse_and_run(configfile):
    
    parsed_args = parse_config(configfile)
    main_search(parsed_args)
    print("SEARCH COMPLETE")
    
    

if __name__=="__main__":
    
    #User hard-coded configfile path
    configfile = Path(r"fy18_test_config.txt")
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
        print(f"Configfile read in as {configfile}")

    else: #if not via command line, specify configfile path here
        print(f"Config file hard-coded and specified as {configfile}")
    if not configfile:
        raise ValueError("You must specify a config file either hard-coded in main or via a config file")
    parse_and_run(configfile)

        
        

