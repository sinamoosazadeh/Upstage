from apex.telegram.control_plane import validate_export_request
for path in ('/Download/APEX_Reports_evil/x.csv','/Download/APEX_Reports/../escape.csv','/Download/APEX_Reports/ok.csv'):
    result=validate_export_request(items=['Positions'],time_range='24h',environment='PAPER',fmt='CSV',path=path)
    print(path,'valid=',result['valid'],'errors=',result['errors'])
