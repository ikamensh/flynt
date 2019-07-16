var, a, b = 12345, 4, "Beew"
my_string = ("Hello %s %s %s".format(var,
                                     a,
                                     b # <<<< busted
                                     ))
var2 = "Some Value"