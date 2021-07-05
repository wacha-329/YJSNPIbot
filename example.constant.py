from enum import Enum

default_debugmode = False
log_file_exist = True

ssh_ip = 'serverip'
ssh_username = 'serverusername'
ssh_password = 'serverpassword'

token = 'token'

bot_author_id = 0

bot_channel_id = 0
notification_channel_id = 0

debug_role_id = 0
notification_role_id = 0
general_channel_id = 0

debug_role_id = 0
notification_role_id = 0

ini_file = 'status.ini'

run_ark_path = r'example'

run_mine_knee_path = r'example'
run_mine_knee_bat = r'example'

run_mine_wolf_path = r'example'
run_mine_wolf_bat = r'example'

run_mine_vanilla_path = r'example'
run_mine_vanilla_bat = r'example'

stop_ark_path = 'ark_stop_setup.bat'

bot_restart_exe_name = 'restart-YJSNPIbot.exe'

class mine_rcon_host(Enum):
    knee = 'example'
    wolf = 'example'
    vanilla = 'example'

class mine_rcon_port(Enum):
    knee = 0
    wolf = 0
    vanilla = 0

class mine_rcon_pass(Enum):
    knee = 'example'
    wolf = 'example'
    vanilla = 'example'