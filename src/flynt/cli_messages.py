from colorama import Style


CREDIT = (
    " Flynt only wraps the pyupgrade "
    f"call and gives stats, all credit goes to original authors of pyupgrade."
)

PYUP_FEATURES_LINK = "https://github.com/asottile/pyupgrade#implemented-features"

MESSAGE_SUGGEST_PYUP = (
    f"{Style.DIM}\nYour code is now compatible only with python versions 3.6 or higher."
    f" Would you like to remove legacy expressions and get a bunch of best practice "
    f"changes for free? Run {Style.BRIGHT}flynt --upgrade [file(s) and/or folder(s)]"
    f" {Style.RESET_ALL}{Style.DIM} to run pyupgrade on all .py files. "
    f"See full list of upgradable expressions at:"
    f" {PYUP_FEATURES_LINK}. {CREDIT}\n{Style.RESET_ALL}"
)

MESSAGE_PYUP_SUCCESS = (
    f"{Style.DIM}\n\nYour code is now pyupgraded!"
    f" See full list of modified expressions at: {PYUP_FEATURES_LINK}."
    f"{CREDIT}\n{Style.RESET_ALL}"
)

FAREWELL_MESSAGE = (
    "Please run your tests before commiting. Report bugs as github issues at: "
    "\n~ https://github.com/ikamensh/flynt ~"
    "\nThank you for using flynt. Upgrade more projects and recommend it to your colleagues!\n"
)
