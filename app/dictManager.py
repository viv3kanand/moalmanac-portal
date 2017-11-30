import pandas as pd
import moment
from datetime import datetime
import requests
#from csportalRequests import firecloud_requests

class statusDict(object):
    @staticmethod
    def new_dict():
        return {'google_status': 'danger', 'firecloud_status': 'danger', 'billing_status': 'danger'}

    @staticmethod
    def return_success():
        return "success"

    @staticmethod
    def return_danger():
        return "danger"

class userDict(object):
    @staticmethod
    def new_dict():
        return {'userinfo': '', 'email': '', 'user': ''}

    @staticmethod
    def populate_googleauth(dict, google):
        dict['userinfo'] = google.get('userinfo')
        dict['email'] = dict['userinfo'].data['email']
        dict['user'] = dict['email'].split('@')[0]
        return dict

class workspaceDict(object):
    @staticmethod
    def format_workspace_description(description):
        return str(description.replace("\r\n", "\n"))

    @staticmethod
    def to_str(notstring):
        return str(notstring)

    @classmethod
    def create_workspace_name(cls, patient):
        name = cls.to_str(patient['tumorTypeShort']) + '_'
        name += cls.to_str(patient['patientId']) + '_'
        name += cls.to_str(datetime.now().strftime('%Y-%m-%d')) + '_'
        name += cls.to_str(datetime.now().strftime('%H-%M-%S'))
        return name

    @classmethod
    def populate_workspace_json(cls, patient):
        json = {
            "namespace": cls.to_str(patient['billingProject']),
            "name": cls.create_workspace_name(patient),
            "attributes": {
                "description": cls.format_workspace_description(patient['description']),
                "tag:tags": {u'items': [u'Chips&SalsaPortal'], u'itemsType': u'AttributeValue'},
                "patientId": cls.to_str(patient['patientId']),
                "tumorTypeShort": cls.to_str(patient['tumorTypeShort']),
                "tumorTypeLong": cls.to_str(patient['tumorTypeLong'])
            },
            "authorizedDomain": []
        }
        return json

    @classmethod
    def populate_gsBucket(cls, workspace):
        json = workspace.json()
        json['bucketId'] = str(json['bucketName'])
        json['bucketHandle'] = 'gs://' + json['bucketId'] + '/'
        return json

class dataModelDict(object):
    @staticmethod
    def df_to_str(df):
        return df.to_csv(sep='\t', index=False)

    @classmethod
    def create_participant_tsv(cls, patient):
        patientId = patient['patientId']
        disease = patient['tumorTypeShort']
        df = pd.DataFrame(columns=['entity:participant_id', 'disease'], index=[0])
        df.loc[0, 'entity:participant_id'] = patientId
        df.loc[0, 'disease'] = disease
        return cls.df_to_str(df)

    @classmethod
    def create_sample_tsv(cls, patient):
        tumor_sample = patient['patientId'] + '-tumor'
        normal_sample = patient['patientId'] + '-normal'

        _columns = ['entity:sample_id', 'participant_id']
        df = pd.DataFrame(columns=_columns)

        df.loc[0, 'entity:sample_id'] = tumor_sample
        df.loc[1, 'entity:sample_id'] = normal_sample
        df.loc[:, 'participant_id'] = patient['patientId']
        df.loc[:, 'disease'] = patient['tumorTypeShort']
        return cls.df_to_str(df)

    @classmethod
    def create_pair_tsv(cls, patient, workspace_dict):
        _columns = ['entity:pair_id', 'participant_id', 'case_sample', 'control_sample',
                    'snvHandle', 'indelHandle', 'segHandle', 'fusionHandle',
                    'burdenHandle', 'germlineHandle', 'dnarnaHandle']
        df = pd.DataFrame(columns=_columns, index=[0])
        tumor_sample = patient['patientId'] + '-tumor'
        normal_sample = patient['patientId'] + '-normal'
        google_bucket = workspace_dict['bucketHandle']

        df.loc[0, 'entity:pair_id'] = patient['patientId'] + '-pair'
        df.loc[0, 'participant_id'] = patient['patientId']
        df.loc[0, 'case_sample'] = tumor_sample
        df.loc[0, 'control_sample'] = normal_sample

        for column_ in _columns[4:]:
            if patient[column_].filename != '':
                df.loc[0, column_] = google_bucket + patient[column_].filename
        return cls.df_to_str(df)

class submissionDict(object):
    @staticmethod
    def request_to_json(request):
        return request.json()

    @staticmethod
    def return_submissionId(json):
        return str(json['submissionId'])

    @staticmethod
    def return_workflowId(json):
        return str(json['workflows'][0]['workflowId'])

    @classmethod
    def extractSubmissionId(cls, request):
        json = cls.request_to_json(request)
        return cls.return_submissionId(json)

    @classmethod
    def extractWorkflowId(cls, request):
        json = cls.request_to_json(request)
        return cls.return_workflowId(json)

    @staticmethod
    def create_attributesTsv(submissionId):
        df = pd.DataFrame({'workspace:submissionId':submissionId}, index=[0])
        return df.to_csv(sep='\t', index=False)

class patientTable(object):
    patientTable_cols = ['namespace', 'name', 'url', 'time', 'createdDate', 'tumorTypeShort', 'tumorTypeLong' 'patientId',
                         'description', 'runningJobs', 'completed']

    @staticmethod
    def subset_tagged_workspaces(all_workspaces):
        return [wkspace for wkspace in all_workspaces if "tag:tags" in wkspace['workspace']['attributes']]

    @staticmethod
    def subset_csPortal_workspaces(tagged_workspaces):
        return [wkspace for wkspace in tagged_workspaces if u'Chips&SalsaPortal' in wkspace['workspace']['attributes']['tag:tags']['items']]

    @staticmethod
    def create_workspace_url(namespace, workspace_name):
        return "https://portal.firecloud.org/#workspaces/" + str(namespace) + "/" + str(workspace_name)

    @staticmethod
    def convert_time(createdDate):
        return datetime.strptime(createdDate, "%Y-%m-%dT%H:%M:%S.%fZ")\

    @staticmethod
    def get_monitor_submission(headers, namespace, name, submissionId):
        request = "https://api.firecloud.org/api/workspaces/"
        request += namespace + '/' + name + '/'
        request += 'submissions/' + submissionId
        r = requests.get(request, headers=headers)
        return submissionDict.extractWorkflowId(r)

    @staticmethod
    def create_reportUrl(bucketName, submissionId, workflowId, patientId):
        url = 'https://storage.cloud.google.com/' + bucketName + '/' + submissionId + '/CHIPS/' + workflowId
        url += '/call-chipsTask/' + patientId + '.report.html'
        return url

    @classmethod
    def format_workspace(cls, workspace, headers):
        workspace_values = workspace['workspace']
        namespace_ = workspace_values['namespace']
        name_ = workspace_values['name']
        created_date_ = workspace_values['createdDate']
        attributes_ = workspace_values['attributes']
        submission_ = workspace['workspaceSubmissionStats']

        df = pd.DataFrame(columns = cls.patientTable_cols)
        df.loc[0, 'namespace'] = str(namespace_)
        df.loc[0, 'name'] = str(name_)
        df.loc[0, 'url'] = cls.create_workspace_url(namespace_, name_)
        df.loc[0, 'bucketName'] = str(workspace_values['bucketName'])
        df.loc[0, 'createdDate'] = str(created_date_)
        df.loc[0, 'time'] = cls.convert_time(df.loc[0, 'createdDate'])
        df.loc[0, 'tumorTypeShort'] = attributes_['tumorTypeShort'].upper()
        df.loc[0, 'tumorTypeLong'] = attributes_['tumorTypeLong']
        df.loc[0, 'patientId'] = attributes_['patientId']
        df.loc[0, 'description'] = attributes_['description']
        df.loc[0, 'submissionId'] = attributes_['submissionId']
        df.loc[0, 'runningJobs'] = submission_['runningSubmissionsCount']
        df.loc[0, 'completed'] = 'lastSuccessDate' in submission_.keys()
        df.loc[0, 'workflowId'] = ''
        df.loc[0, 'reportUrl'] = ''
        if df.loc[0, 'completed']:
            df.loc[0, 'workflowId'] = cls.get_monitor_submission(headers, df.loc[0, 'namespace'], df.loc[0, 'name'], df.loc[0, 'submissionId'])
            df.loc[0, 'reportUrl'] = cls.create_reportUrl(df.loc[0, 'bucketName'], df.loc[0, 'submissionId'],
                                                          df.loc[0, 'workflowId'], df.loc[0, 'patientId'])
        return df

    @classmethod
    def generate_patientTable(cls, all_workspaces, headers):
        tagged_workspaces = cls.subset_tagged_workspaces(all_workspaces)
        csPortal_workspaces = cls.subset_csPortal_workspaces(tagged_workspaces)

        patientTable = pd.DataFrame(columns = cls.patientTable_cols)
        for workspace_ in csPortal_workspaces:
            patientTable = patientTable.append(cls.format_workspace(workspace_, headers), ignore_index = True)

            patientTable.to_csv('patientTable.txt', sep = '\t')
        return patientTable.sort_values(['createdDate'], ascending = False)

class oncoTree(object):
    # http://oncotree.mskcc.org/oncotree/#/home oncotree_2017_06_21
    oncotreePath='app/static/files/oncotree_chipssalsa_dict.txt'

    @classmethod
    def import_oncotree(cls):
        return pd.read_csv(cls.oncotreePath, sep='\t')

    @classmethod
    def return_tumorTypes(cls):
        df = cls.import_oncotree()
        return df['tumorType'].tolist()

    @classmethod
    def create_oncoTree(cls):
        tumorTypeList = cls.return_tumorTypes()
        list_ = []
        for ontology in tumorTypeList:
            list_.append(str(ontology))
        return list_

    @classmethod
    def extract_shortcode(cls, ontology):
        oncotree = cls.return_tumorTypes()
        if ontology in oncotree:
            shortcode = str(ontology).split('(')[1].split(')')[0]
            return str(shortcode)
        else:
            return ontology

    @classmethod
    def extract_longcode(cls, ontology):
        oncotree = cls.return_tumorTypes()
        if ontology in oncotree:
            longcode = str(ontology).split(' (')[0]
            return str(longcode)
        else:
            return ontology
