import sys
import math

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
    print(findSharedLevel(3,2,2))