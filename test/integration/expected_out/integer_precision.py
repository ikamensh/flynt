hexadecimal = "%4.4x" % (value,)
octal = "%#8.4o" % value
mapping = "%(value)+8.4X" % {"value": value}
decimal = "%.4d" % int(value)
floating = f"{value:.4f}"
integer = f"{value:08x}"
