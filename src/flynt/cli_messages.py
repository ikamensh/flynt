from colorama import Style


credit = (
    " Flynt only wraps the pyupgrade "
    f"call and gives stats, all credit goes to original authors of pyupgrade."
)

pyup_features_link = "https://github.com/asottile/pyupgrade#implemented-features"

message_pyup_success = (
    f"{Style.DIM}\n\nYour code is now pyupgraded!"
    f" See full list of modified expressions at: {pyup_features_link}."
    f"{credit}\n{Style.RESET_ALL}"
)

farewell_message = (
    "Please run your tests before commiting. Did flynt get a perfect conversion? give it a star at: "
    "\n~ https://github.com/ikamensh/flynt ~"
    "\nThank you for using flynt. Upgrade more projects and recommend it to your colleagues!\n"
)
