lst = [2, 3, 4]
a = "beautiful numbers to follow: {}".format(" ".join(lst))
a = "beautiful numbers to follow: {}".format("\t".join(lst))
a = "beautiful numbers to follow: {}".format(' '.join(lst))
a = "beautiful numbers to follow: {}".format('\n'.join(lst))


b = 'beautiful numbers to follow: {}'.format(" ".join(lst))
b = 'beautiful numbers to follow: {}'.format("\n".join(lst))
b = 'beautiful numbers to follow: {}'.format(' '.join(lst))
b = 'beautiful numbers to follow: {}'.format(','.join(lst))