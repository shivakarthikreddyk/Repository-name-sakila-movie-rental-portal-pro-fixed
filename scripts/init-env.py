"""Create local credentials once without printing or replacing passwords."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / '.env'
try:
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(f'DB_PASSWORD={secrets.token_hex(24)}\n')
        output.write(f'MYSQL_ROOT_PASSWORD={secrets.token_hex(24)}\n')
        output.write('APP_PORT=8092\nAPP_BIND_ADDRESS=127.0.0.1\n')
    path.chmod(0o600)
    print('Created .env with unique local database passwords.')
except FileExistsError:
    print('Using existing .env; credentials were not changed.')
