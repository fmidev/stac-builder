import re
import boto3
import json
import argparse

def connection_tester(conf, s3client):
    '''
    Function tests if files can be found from S3 bucket with given S3 key prefixes.
    S3 key prefixes are fetched from the dataset's configuration file.
    Test prints a list of found paths.
    Test prints a list of problematic S3 prefixes.
    '''
    
    fileNamingConvention = conf["item"]["fileNamingConvention"]
    blacklist = conf["blacklist"]
    
    s3Bucket = conf["source"]["s3Bucket"]
    s3Prefixes = conf["source"]["s3Prefixes"]
    publicUrlPrefix = conf["source"]["publicUrlPrefix"]
    problem_list = []

    for s3Prefix in s3Prefixes:
        nextToken = ''
        print("Current s3 prefix:", s3Prefix)

        try:
            while True:
                response = s3client.list_objects_v2(Bucket=s3Bucket, Prefix=s3Prefix, ContinuationToken=nextToken)

                for file in response['Contents']:
                    url = publicUrlPrefix + file['Key']
                    
                    # Check if url is in blacklist
                    if url in blacklist: 
                        continue

                    filename = url.split("/")[-1] # extract filename from url

                    # Find date and band from filename using fileNameConvention
                    # and regular expressions (regex: https://docs.python.org/3/howto/regex.html)
                    p = re.compile(fileNamingConvention)
                    m = p.search(filename)
                    
                    try: # Check if filename is in expected format
                        m.group('startdate')
                        try:
                            m.group('band')
                        except:
                            pass
                        try:
                            m.group('enddate')
                        except IndexError: # if the filename does not contain an enddate
                            pass 
                        try:
                            m.group('starttime')
                            m.group('endtime')
                        except IndexError:
                            pass
                        try:
                            m.group('tile')
                        except:
                            pass
                    except AttributeError: # if filename does not match expected format
                        continue
                    print(url, "was found.")
                
                if 'NextContinuationToken' in response:
                    nextToken = response['NextContinuationToken']
                else:
                    break
        except:
            print("An error occurred with prefix", s3Prefix)
            problem_list.append(s3Prefix)
            
    print("******************************* Test is done! *******************************")
    if len(problem_list) == 0:
        print("No errors occurred in test.")
    else:
        print("There was some error with the following S3 prefixes:")
        for prefix in problem_list:
            print(prefix)

def start_test():
    parser = argparse.ArgumentParser(description='S3 connection tester.')
    parser.add_argument("dataset_configuration_file", help="Location of the dataset's configuration file")
    parser.add_argument("s3_configuration_file", help="Location of the s3 configuration file")
    args = parser.parse_args()
    dataset_configuration_file = args.dataset_configuration_file
    s3_configuration_file = args.s3_configuration_file
    
    # Dataset configuration file
    conf_f = open(dataset_configuration_file)
    conf = json.load(conf_f)

    # S3 configuration file
    conf_s3_f = open(s3_configuration_file)
    conf_s3 = json.load(conf_s3_f)

    client = boto3.client('s3', 
            aws_access_key_id = conf_s3['aws_access_key_id'],
            aws_secret_access_key = conf_s3['aws_secret_access_key'],
            endpoint_url = conf_s3['endpoint_url']
        )
    print("Dataset configuration file location:", dataset_configuration_file)
    print("S3 configuration file location:", s3_configuration_file)
    print("******************************* Test begins. *******************************")

    # Test connection
    connection_tester(conf, client)

start_test()