OUTPUT_FILE = "{home}/{name}.txt"
STATUS_CMD = f"echo \"SCREEN_EXIT:$?\" ; echo \"{END_OF_STREAM}\"\n"
ENTRY_CMD = f"echo \"{START_STREAM}\""
SCREEN_TIMEOUT = 3600  # seconds
