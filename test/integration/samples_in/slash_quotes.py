OUTPUT_FILE = "{home}/{name}.txt"
STATUS_CMD = "echo \"SCREEN_EXIT:$?\" ; echo \"{EOS}\"\n".format(EOS=END_OF_STREAM)
ENTRY_CMD = "echo \"{}\"".format(START_STREAM)
SCREEN_TIMEOUT = 3600  # seconds
