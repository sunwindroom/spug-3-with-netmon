from apps.account.models import User
u = User.objects.filter(is_supper=True).first()
if u:
    print(f'id={u.id} username={u.username} token={u.access_token}')
else:
    print('No superuser found')
