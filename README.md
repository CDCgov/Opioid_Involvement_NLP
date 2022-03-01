# FY18_pcortf_nlp

FY18 Opioid Search in Clinical Notes

Git ReadMe Draft

Author: Nikki Adams; oxf7@cdc.gov

Last update: February 28, 2022

This is the first release of the code used to analyze the clinical notes from the 2016 National Hospital Care Survey (NHCS) data for the fiscal year (FY) 2018 Office of the Secretary-Patient-Centered Outcomes Research Trust Fund-funded project on the identification of opioid-involvement in hospitalizations and emergency department visits. The National Center for Health Statistics conducts NHCS which involves the collection of a participating hospital’s (UB)-04 administrative claims records or electronic health records (EHR) in a 12-month period. For a hospital to be eligible for NHCS, the hospital must be a non-federal, non-institutional hospital with 6 or more staffed inpatient beds. The FY 2018 project had a capstone project in FY 2019, which identified hospital encounters with substance use disorders (SUD) and mental health issues (MHI). In the complete algorithm, it was from these opioid-involved encounters that MHIs and SUDs were searched. This repository contains only the opioid-involvement search, not the SUD and MHI search, which is located here. The goal of this code is to flag opioid involvement and overdoses in free text clinical notes. The code to flag opioid-involvement, SUD, and MHI in hospital encounters by medical codes from structured data is located here. Detailed information on the project can be obtained for the opioid-involvement portion of the project, here: 

https://www.cdc.gov/nchs/data/series/sr_02/sr2-188.pdf

This file contains mappings for child categories under the parent category of Opioid Involvement. In order to calculate the final counts for the parent categories, after running the code, these parent categories can be created by counting all observations where any value in the child category (e.g. CODEINE) creates a positive flag in the parent category (e.g. OP_INVOLVED). For more information, see the data dictionary and description here:

https://www.cdc.gov/nchs/data/nhcs/Task-3-Doc-508.pdf



**Usage**

All options for this code are specified in a config file, the format of which is explained in detail below. Once the config file is properly set up, the code can be run either by hard-coding in the config file path in the main portion of the code or by passing in the config file path as a command line argument.

Option 1 – Hard coded 
Hard-coded: Look in the main code (NCHS_PCORTF_NLP_OPIOID.py) for these lines and put the path where indicated: 

#User hard-coded configfile path 
```python
configfile = Path(r"fy18_test_config.txt")  
```

Option 2 – Command line argument 

At a command line type: 
```shell
python NCHS_PCORTF_NLP_OPIOID.py config_file_path_here 
```


An example input CSV is shown below:
| UNIQUE_ID | STATE | LITERAL_TEXT | MEDICARE |
| ------ | ------ | ------ | ------ |
| 123X | ALASKA | "Alaska resident prescribed oxycodone" | 1 |
| 456X | ALASKA | "Alaska resident had several refills of oxycodone" | 0 |
| 789Y | MICHIGAN | "Denies having used morphine | 1 |

An example of the term-to-variable mappings is shown below (search is case-insensitive)::

| Term | Category |
| ------ | ------ |
| morphine | morphine |
| Oxycodone | OXYCODONE |

With a config setting to exclude MEDICARE=0

With an example output as below:

| UNIQUE_ID | STATE | MORPHINE | OXYCODONE | OTH_OPIOID | OTH_TERMS_LIST | OVERDOSE |
| ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| 123X | ALASKA | 0 | 1 | 0 |  | 0 |


Where the first observation in the input is flagged for oxycodone, the second observation in the input is excluded from any flags because an exclusion of MEDICARE = 0 was set, and the third observation has no flags because the drug term "morphine" is negated by "denies". The config file was set for output_zeros = False, meaning that observations with no flags are not output.

**Package Requirements**


Running this code requires Python >= 3.4. 


- [negex_adjusted.py](negex_adjusted.py) (modified from original) 
- [build_queries.py](build_queries.py) 
- [negation_triggers.txt](data/negation_triggers.txt) 
- keywords and their mappings as well as a sample input file and sample config file in [data](data/)


**Install 3rd party packages** 

All requirements can be installed via the included requirements.txt document with: 
    pip install requirements.txt

or if using Anaconda, within your desired environment: 
    conda install --file requirements.txt 

The necessary 3rd party packages in the requirements file are listed below, but spaCy is only needed if  using named entity recognition NER (which here, is only implemented for date year exclusion). Pyodbc is only needed if the input is from a SQL database. 

    nltk >=3.4 
    pyodbc >=4.0 
    spacy >=2.0


The original code for negex was obtained from: 

https://github.com/chapmanbe/negex/blob/master/negex.python/negex.py 

but we altered the code slightly to allow both forward and backward-looking negation for the same negation trigger, so we recommend using the negex_adjusted.py included in this repository. 

The sent_tokenize() function used here from NLTK installs in a lazy fashion, meaning that the code is installed but the necessary model is not downloaded until called. Prior to running this code, a user can type the below in an interpreter in the appropriate environment to force use of the model. NLTK will then give prompts for downloading the model: 

    from nltk.tokenize import sent_tokenize 
    sent_tokenize("Hello.") 


SpaCy is only needed if the NER is used, and NER is only implemented in this version for date exclusion; in the algorithm as performed on the National Hospital Care Survey. It was also used to detect drug terms, but that model cannot be released at this time. The spacy model to use NER will also have to be downloaded before use. A base English model can be downloaded at a command line by typing: 

    python -m spacy download en_core_web_sm 

After download, specify the path to where the model is installed. It should be the parent folder that contains the “ner” folder. If that is unclear, in the environment in which the model was downloaded, type the information below and it will output the path to the model. 

    import spacy 
    nlp = spacy.load("en_core_web_sm") 
    nlp.path 



**Input and Output Files**

Three files are needed to serve as input for this package, and it will produce 2 output files.

_Input file #1_ – Source data 

This package will accept two types of input data: (1) a csv file, with column names as the first row or (2) a table in Microsoft SQL for Windows. In theory, connecting to SQLite and possible other databases should work the same using the pyodbc package used here with the code as we have currently written it, but only csv and Microsoft SQL Server 2016 have been tested. 

_Input file #2_ – Term mapping 

This file is a csv file where the first column is the phrase to be searched for and the second column is the output variable to be flagged, if that term is found. Below is an example of the first 2 lines of what this file should look like 

    Oxycontin,Oxycodone 
    6-mam,Heroin


When “oxycontin” is found, there will be an output variable OXYCODONE that will have a ‘1’ in it for the row in which “oxycontin” was found. Note that there is a special variable name, "OTH_OPIOID", for which the values of the variables are not integers as with other variables, but rather a semi-colon-delimted list of the exact terms that matched for that flag.

_Input file #3_ – Config file 

This file specifies where the input files are, where the output files will go, and other allowed options. A sample config file is included in this repository, but every option is explained in the next section.

_Output file #1_ – Results file 

This file will have the results of the term search 

_Output file #2_ – log file 

This file will print status updates on the search, printing an update every 100,000 rows of search, along with a final completion message. 


**Setting Up Your Config File** 

Below is a sample of a properly-formatted config file. Note that values should not include quotation marks. This example shows input coming from a SQL database, while the example config file provided in the data/ folder is for input from a CSV.

    [INPUT_SETTINGS] 
    input_type = DB
    cnxn_string = DRIVER={SQL Server}; SERVER=DSPV-INFC-CS161\PROD; DATABASE=MyDB_2018; Trusted_Connection=yes 
    cursor_execute_string = SELECT * FROM MyDB_2018.dbo.MYDB 
    csv_input_file =  

    [TERMS] 
    search_terms_path = data\FY18_term_ mappings.txt 
    negex_triggers_path = data\negex_triggers.txt 

    [OUTPUT] 
    results_file = data\FY18_test_out.txt 
    logging_file = data\FY18_logfile.txt 

    [SEARCH_CONFIG] 
    col_to_search = LITERAL_TEXT 
    output_columns = UNIQUE_ID, STATE 
    upfront_val_exclusions = STATE, Nebraska 
    upfront_val_inclusions = MEDICARE, 1
    upfront_string_exclusions = patient education 
    NER_model  = C:\yourpath\en_core_web_sm\en_core_web_sm-3.0.0
    year_excluded =
    custom_date_exclusion = '\bJan(uary)?\W{1,2}(20)?18\b' 
    overdose = True 
    exclusion_terms = data\drug_exclusions.txt 

Included above are all available options, with examples. The text below provides further explanation on every option and whether it is required or optional.

    [INPUT_SETTINGS] 
    input_type: REQUIRED. Options are CSV for a csv file or DB for database connection. 
    cnxn_string: REQUIRED if input_type=DB. The string used to connect to the database through pyodbc. 
    cursor_execute_string: REQUIRED if input_type=DB. The query select string. 
    csv_input_file: REQUIRED if input_type=CSV. The path to the input csv file. 

    [TERMS] 
    search_terms: REQUIRED. Path to a 2-column csv file of search term/phrase and column, which will be flagged when that term is found. This command will search for terms with word boundaries on either side but does allow a final “*” to indicate no word-boundary on right side. 
    negex_triggers_path: REQUIRED. Path to the negex triggers file. A file is included but can be modified at user discretion. These are the negation triggers (“not”, “denies”, etc.) 

    [OUTPUT] 
    results_file: REQUIRED. Path to the output file. Output is csv format. 
    logging_file: REQUIRED. Path to where logging messages about output will print. 

    [SEARCH_CONFIG] 
    col_to_search: REQUIRED. Identifies which column the term searches are performed in. Case-insensitive. 

    output_columns: OPTIONAL. A comma-separated list of which columns (e.g. unique identifiers or linkage variables) should be output with each result. Case-insensitive. 

    upfront_val_exclusions: OPTIONAL. A comma-separated list of at least length 2. The first item is the column in which the exclusion is to be searched for. Positions 1 to end are all the values to exclude. For example, entering: “STATE, ALABAMA, Alaska” (no quotes) would exclude any rows for which the value in column STATE equals “ALABAMA” or “ALASKA”. Case-insensitive. The value of the cell must equal the exclusion, i.e. this is not a substring search.
        
    upfront_val_inclusions: OPTIONAL. A comma-separated list of at least length 2. The first item is the column in which the inclusion is to be searched for. Positions 1 to end are all the values to include. For example, entering: “STATE, ALABAMA, Alaska” (no quotes) would include only rows for which the value in column STATE equals “ALABAMA” or “ALASKA”. Case-sensitive. The value of the cell must equal the inclusion, i.e. this is not a substring search.

    upfront_string_exclusions: OPTIONAL. A comma-separated list of any strings that, if found, exclude that row from being searched for any of the search terms. Case-insensitive. These are regular expression searches and thus can occur anywhere in the cell (unlike upfront_val_exclusions). These exclusions are only searched for in the same col as col_to_search 

    NER_model: OPTIONAL. NER only used currently for date exclusions. 

    year_excluded: OPTIONAL, but either this or custom_date_exclusion is REQUIRED if NER_model is specified. To exclude a single year, type in the 4-digit year here 

    custom_date_exclusion: OPTIONAL, but either this or year_excluded is REQUIRED if NER_model is specified. For a regular expression date exclusion beyond just a year, put it here. 

    overdose: REQUIRED. Enter either True or False, True to search for overdose.

    exclusion_drugs: REQUIRED if overdose=True. Path to terms, one per line, to be used used as alternative overdose drugs. If overdose=True, first an overdose term is searched for in conjunction with terms specified in [TERMS][search_terms]. If that combination is not found in the same sentence, a combination of an overdose term and an exclusion drug is then tried before going on to search previous and following contexts overdose and [TERMS][search_terms]. 

    output_zeros: OPTIONAL. Default will be false, so if this is desired, it must be specified. If true, there will be an output for every input observation, regardless of whether anything was found. If false, only rows where something was positively flagged will be output.




**Licenses and Disclaimers**

**Public Domain**

This repository constitutes a work of the United States Government and is not subject to domestic copyright protection under 17 USC § 105. This repository is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/). All contributions to this repository will be released under the CC0 dedication. By submitting a pull request you are agreeing to comply with this waiver of copyright interest.

**License**

The repository utilizes code licensed under the terms of the Apache Software License and therefore is licensed under ASL v2 or later.

This source code in this repository is free: you can redistribute it and/or modify it under the terms of the Apache Software License version 2, or (at your option) any later version.

This source code in this repository is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the Apache Software License for more details.

You should have received a copy of the Apache Software License along with this program. If not, see http://www.apache.org/licenses/LICENSE-2.0.html

The source code forked from other open source projects will inherit its license.

**Privacy**

This repository contains only non-sensitive, publicly available data and information. All material and community participation is covered by the Surveillance Platform [Disclaimer](https://github.com/CDCgov/template/blob/master/DISCLAIMER.md) and [Code of Conduct](https://github.com/CDCgov/template/blob/master/code-of-conduct.md). For more information about CDC's privacy policy, please visit http://www.cdc.gov/privacy.html.

**Contributing**

Anyone is encouraged to contribute to the repository by [forking](https://help.github.com/articles/fork-a-repo) and submitting a pull request. (If you are new to GitHub, you might start with a [basic tutorial](https://help.github.com/articles/set-up-git).) By contributing to this project, you grant a world-wide, royalty-free, perpetual, irrevocable, non-exclusive, transferable license to all users under the terms of the [Apache Software License v2](http://www.apache.org/licenses/LICENSE-2.0.html) or later.

All comments, messages, pull requests, and other submissions received through CDC including this GitHub page are subject to the [Presidential Records Act](http://www.archives.gov/about/laws/presidential-records.html) and may be archived. Learn more at http://www.cdc.gov/other/privacy.html.

**Records**

This repository is not a source of government records, but is a copy to increase collaboration and collaborative potential. All government records will be published through the [CDC web site](http://www.cdc.gov/).

**Notices**

Please refer to [CDC's Template Repository](https://github.com/CDCgov/template) for more information about [contributing to this repository](https://github.com/CDCgov/template/blob/master/CONTRIBUTING.md), [public domain notices and disclaimers](https://github.com/CDCgov/template/blob/master/DISCLAIMER.md), and [code of conduct](https://github.com/CDCgov/template/blob/master/code-of-conduct.md).


