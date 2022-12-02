name = 'mari'

a = "Setting %20r must be uppercase." % name

print(a)

i = 10
b = '_%03X' % i
print(b)

coord = (1, 2)
c = '%f %f' % (coord[1], coord[0])
print(c)

d = '%i' % i
e = '%.03f' % i

print(d,e)

print(f"{a} hello")
