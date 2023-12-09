import sys
import math
import random
import time

def reverseBit(value, loc):
    """
    reverse the last loc bit
    """
    res = 0
    for i in range(1, loc+1):
        res <<= 1
        tmpV = (value&(1<<(i-1)))>>(i-1)
        res ^= tmpV
    return res

def findSharedLevel(loc0,loc1,treeHeight): # Tree: 0,1,...,treeHeight
    shiftTimes = 0
    while loc0!=loc1:
        loc0>>=1
        loc1>>=1
        shiftTimes+=1
    return treeHeight-shiftTimes

def update_loading_bar(progress):
    bar_length = 50
    block = int(round(bar_length * progress))
    progress_percent = progress * 100
    bar = "#" * block + "-" * (bar_length - block)

    sys.stdout.write(f"\r[{bar}] {progress_percent:.1f}%")
    sys.stdout.flush()

if __name__=="__main__":
    print((4<<1)-1)

    pp = ["da","ds"]
    print(pp[1]=="ds")
    pL = [3,5]
    po = [(1565, b'5\xe3\xa2P\x08\x07x\xae\xd2\xa8\xd4\xb4\xdd\xacg\x05'),(15365, b'5\xe3\xa2P\x08\x07x\xae\xd2\xa8\xd4\xb4\xdd\xacg\x05'),(15265, b'5\xe3\xa2P\x08\x07x\xae\xd2\xa8\xd4\xb4\xdd\xacg\x05')]
    po.remove((1565, b'5\xe3\xa2P\x08\x07x\xae\xd2\xa8\xd4\xb4\xdd\xacg\x05'))

    print(po)

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
    #print(findSharedLevel(3,2,2))