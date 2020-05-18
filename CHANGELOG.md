v.0.47

* added the changelog.
* added `-a / --aggressive` flag to enable risky 
(with behaviour potentially different from original) transformations. 
This currently includes only "%5" % var -> f"{var:5}" transformation. 
Demo of unsafe behavior: 

```
print( "|%5s|%5d|%5d|" % ('111', 999_999, 77)  )
print( "|%5d|%5d|%5d|" % (111, 999_999, 77)  )

print( "|{:5s}|{:5}|{:5}|".format('111', 999_999, 77)  )
print( f"|{111:5}|{999_999:5}|{77:5}|" )

""" output:
|  111|999999|   77|
|  111|999999|   77|
|111  |999999|   77|  << behavior differs when printing a string
|  111|999999|   77|
"""
```

* added short versions to other flags:
```
--line-length, -l
--transform-concats, -tc
--verbose, -v
--quiet, -q
--fail-on-change, -f
```