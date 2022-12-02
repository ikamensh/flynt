name = 'mari'

a = "Setting %20r must be uppercase." % name

print(a)

i = 10
b = f'_{i:03X}'
print(b)

coord = (1, 2)
c = f'{coord[1]:f} {coord[0]:f}'
print(c)

d = '%i' % i
e = f'{i:.03f}'

print(d,e)

print(f"{a} hello")
