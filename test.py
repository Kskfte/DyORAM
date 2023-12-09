
kLevel = 7
T =4
kLeaf=19

while kLevel>T:
    kLevel -= 1
    kLeaf >>= 1
print(kLevel,kLeaf)
kLevel = 7
T =4
kLeaf=19
if kLevel>T:
    print(kLevel-T)
    kLevel -= (kLevel-T)
    
    kLeaf = kLeaf>>(kLevel-T)


print(kLevel,kLeaf)

mlkl = 5
mlkl >>= (3-1)
print(mlkl)