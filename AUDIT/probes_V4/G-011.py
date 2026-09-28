from apex.telegram.control_plane import ConfirmationRegistry
r=ConfirmationRegistry(clock=lambda:100.0,utc_now=lambda:'2026-01-01T00:00:00.000Z')
a=r.issue('EMERGENCY_L1','123')
first=r.consume(a.key,action='EMERGENCY_L1',chat_id='123',choice='YES')
b=r.issue('EMERGENCY_L1','123')
second=r.consume(a.key,action='EMERGENCY_L1',chat_id='123',choice='YES')
print('same_key=',a.key==b.key,'first=',first,'second_old_key=',second,'stored_nonce_count=',len(r.pending('123')))
