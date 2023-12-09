import sys
import math
import random
import time

def reverseBit(leafID, levelID):
    """
    reverse the last loc bit
    """
    res = 0
    for i in range(1, levelID+1):
        res <<= 1
        tmpV = (leafID&(1<<(i-1)))>>(i-1)
        res ^= tmpV
    return res

def revLexCompare(levelID, nowLeaf, maxLeaf):
    return reverseBit(nowLeaf,levelID)<=reverseBit(maxLeaf,levelID)

def remapPos(maxLeafID, maxLevelID):
    rPos = random.randint(0,2**maxLevelID-1)
    nowLeaf,nowLevel = 0,0
    if revLexCompare(maxLevelID,rPos,maxLeafID):
        nowLeaf,nowLevel = rPos,maxLevelID
    else:
        nowLeaf,nowLevel = rPos>>1,maxLevelID-1
    return nowLeaf,nowLevel

def staticFindSharedLevel(loc0,loc1,treeHeight): # Tree: 0,1,...,treeHeight
    shiftTimes = 0
    while loc0!=loc1:
        loc0>>=1
        loc1>>=1
        shiftTimes+=1
    return treeHeight-shiftTimes

def dynamicFindSharedLevel(leafAndLevel0,leafAndLevel1): # Tree: 0,1,...,treeHeight
    leaf0,level0 = leafAndLevel0
    leaf1,level1 = leafAndLevel1
    levelID = min(level0,level1)
    leaf0 >>= (level0-levelID)
    leaf1 >>= (level1-levelID)
    shiftTimes = 0
    while leaf0!=leaf1:
        leaf0>>=1
        leaf1>>=1
        shiftTimes+=1
    return levelID-shiftTimes

def update_loading_bar(progress):
    bar_length = 50
    block = int(round(bar_length * progress))
    progress_percent = progress * 100
    bar = "#" * block + "-" * (bar_length - block)

    sys.stdout.write(f"\r[{bar}] {progress_percent:.1f}%")
    sys.stdout.flush()


if __name__=="__main__":
    print(reverseBit(3,3))
    #print(findSharedLevel((1,9),(1,9)))
    #print(findSharedLevel((1,9),(1,9)))
    print(3>7)
    print(8&1)
    print(9>>0)
    """"
    print((4<<1)-1)

    pL = [3,5]
    
    print((len(pL)<<1)-1)
    flag = 1
    newV = 9
    bb2 = time.time()
    for i in range(10):
        flag = random.choice([0,1])
        if flag==0:
            pL = (newV,pL[1])
        else:
            pL = (pL[0],newV)
        pL = [3,5]
    ee2 = time.time()

    bb = time.time()
    for i in range(10):
        flag = random.choice([0,1])
        pL = [pL[0]*flag + newV*(flag^1), pL[1]*(flag^1) + newV*flag]
        #print(pL)
        pL = [3,5]
    ee = time.time()

    print(ee-bb)
    print(ee2-bb2)
    """
    
    #print(findSharedLevel(3,2,2))