from exceptions import PydolonsError

class CantAffordActiveError(PydolonsError):

    def __init__(self, active, missing):
        assert missing in ["mana", "stamina", "health"]
        self.active = active
        self.missing = missing

    def __repr__(self):
        return "Need more {} to activate {}".format(self.missing, self.active)