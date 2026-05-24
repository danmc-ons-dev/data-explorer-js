CREATE TABLE IF NOT EXISTS approver ( 
approver_id SERIAL PRIMARY KEY NOT NULL, 
approver_title TEXT, 
approver_forename TEXT  NOT NULL, 
approver_surname TEXT  NOT NULL, 
approver_email_address TEXT  NOT NULL UNIQUE, 
approver_sector TEXT, 
approver_organisation TEXT, 
approver_role TEXT, 
approver_country TEXT, 
approver_last_login TEXT 
);

CREATE TABLE IF NOT EXISTS uploader ( 
uploader_id SERIAL PRIMARY KEY NOT NULL, 
uploader_title TEXT, 
uploader_forename TEXT  NOT NULL, 
uploader_surname TEXT  NOT NULL, 
uploader_email_address TEXT  NOT NULL UNIQUE, 
uploader_sector TEXT, 
uploader_organisation TEXT, 
uploader_role TEXT, 
uploader_country TEXT, 
uploader_permissions TEXT, 
uploader_number_uploads INT  NOT NULL, 
uploader_last_login TEXT, 
approver_id INT  NOT NULL ,  
CONSTRAINT fk_approver_id FOREIGN KEY(approver_id) REFERENCES approver(approver_id) 
);

CREATE TABLE IF NOT EXISTS metadata ( 
indicator_dataset_id SERIAL PRIMARY KEY NOT NULL, 
uploader_id INT  NOT NULL, 
verifier_id INT  NOT NULL, 
data_permissions TEXT  NOT NULL, 
upload_date_time TEXT  NOT NULL, 
upload_file_size float8  NOT NULL, 
upload_n_rows INT  NOT NULL, 
dataset_doi TEXT, 
approval_status TEXT  NOT NULL, 
approved_date_time TEXT ,  
CONSTRAINT fk_uploader_id FOREIGN KEY(uploader_id) REFERENCES uploader(uploader_id), 
CONSTRAINT fk_approver_id FOREIGN KEY(verifier_id) REFERENCES approver(approver_id) 
);

CREATE TABLE IF NOT EXISTS framework ( 
framework_release_id SERIAL PRIMARY KEY NOT NULL, 
framework_version TEXT  NOT NULL UNIQUE, 
release_date TEXT  NOT NULL, 
framework_doi TEXT   UNIQUE 
);

CREATE TABLE IF NOT EXISTS indicator ( 
indicator_id SERIAL PRIMARY KEY NOT NULL, 
indicator_number TEXT  NOT NULL, 
indicator_version INT  NOT NULL, 
indicator_type TEXT  NOT NULL, 
indicator_name TEXT  NOT NULL, 
indicator_topic_area TEXT  NOT NULL, 
indicator_publication_date TEXT  NOT NULL, 
indicator_last_update TEXT  NOT NULL, 
indicator_tier INT  NOT NULL, 
framework_release_id INT  NOT NULL ,  
CONSTRAINT fk_framework_release_id FOREIGN KEY(framework_release_id) REFERENCES framework(framework_release_id) 
);

CREATE TABLE IF NOT EXISTS data ( 
data_row_id SERIAL PRIMARY KEY NOT NULL, 
indicator_dataset_id INT  NOT NULL, 
indicator_id INT  NOT NULL, 
exposure_type TEXT, 
exposure_unit TEXT, 
exposure_value float8, 
outcome_type TEXT  NOT NULL, 
outcome_unit TEXT  NOT NULL, 
outcome_value float8  NOT NULL, 
outcome_value_lower float8, 
outcome_value_higher float8, 
start_year INT  NOT NULL, 
start_month INT, 
start_day INT, 
end_year INT  NOT NULL, 
end_month INT, 
end_day INT, 
geography TEXT  NOT NULL, 
sub_geography TEXT, 
sex TEXT, 
age_group TEXT, 
socioeconomic_group TEXT, 
degree_urbanisation TEXT ,  
CONSTRAINT fk_indicator_dataset_id FOREIGN KEY(indicator_dataset_id) REFERENCES metadata(indicator_dataset_id), 
CONSTRAINT fk_indicator_id FOREIGN KEY(indicator_id) REFERENCES indicator(indicator_id) 
);