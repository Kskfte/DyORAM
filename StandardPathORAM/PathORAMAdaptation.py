import random
import math
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from utils import findSharedLevel
import copy
from utils import update_loading_bar
import time

"""
Client: A(1)
A(1) stores 
Server: T(2), T(3),..., T(L-1), T(L)

Form: 
T(2)->T(L-1): (addr, nextTreePos, leafNum)
T(L): (addr, val, leafNum)

ValTreeHeight = log(N)
ValTreeID = {0,1,2,...,ValTreeHeight-1}
"""
class PathORAMRecursive:
    
    emptyElement = (-1,bytes(16),-1) # (k,v,leafNum): (16-byte, 16-byte, log2(N))
    emptyPos = (-1,(-1,-1),-1) # (k,(nextPos,nextPos),pos): (16-byte, (log2(NextN),log2(NextN)), log2(NowN))
    def __init__(self, N, localMapSize) -> None: # localMapSize: {2,4,8,...}
        self.N = N # InitSize
        self.M = N # CurrentSize
        self.Z = 2
        self.valTreeMaxLevelID = math.ceil(math.log2(N))-1 # 0, 1, ..., self.valTreeMaxLevelID  valTreeHeight
        self.localMapSize = localMapSize
        self.firstPosTreeMaxLevelID = (int)(math.log2(self.localMapSize)) # firstPosTreeMaxLevelID
        """
        Storing in Client
        """
        self.localPosMap = []
        self.posMapStash = [[] for i in range(self.firstPosTreeMaxLevelID, self.valTreeMaxLevelID)]
        self.valStash = []
        """
        Storing in Server
        """
        
        # T(2), T(3),..., T(L-1)
        self.posMapTree = [[[[PathORAMRecursive.emptyPos for _ in range(self.Z)] for _ in range(2**i)] for i in range(j+1)] for j in range(self.firstPosTreeMaxLevelID, self.valTreeMaxLevelID)]
        # T(L)
        self.valTree = [[[PathORAMRecursive.emptyElement for _ in range(self.Z)] for _ in range(2**i)] for i in range(self.valTreeMaxLevelID+1)]
        """
        leaf:
                       0
                0              1
           00      01      10     11 
        000 001 010 011 100 101 110 111
        """
        """
        Overhead
        """
        self.localPosMapStorageInKB = 0 # 4*math.ceil(2//8)/(2**10) # save 4 locations with 4 leaf, each with 2-bit
        self.localStashStorageInKB = 0 #len(self.stash)*(16+math.ceil(math.log2(len(self.posMap)))//8)/(2**10)
        self.bandwidthInKB = 0 #32*2*pORAM.Z*(pORAM.valTreeMaxLevelID+1)/(2**10)

    def writePosTree(self, posList, posTree):
        leafNum = len(posTree[len(posTree)-1])
        tempPosMap = {}
        for (k,v) in posList:
            rPos = random.randint(0,leafNum-1)
            tempPosMap[k] = rPos
            nowLevelPos = rPos
            findPos = False
            for level in range(len(posTree)-1,-1,-1):
                if PathORAMRecursive.emptyPos in posTree[level][nowLevelPos]:
                    posTree[level][nowLevelPos][posTree[level][nowLevelPos].index(PathORAMRecursive.emptyPos)] = (k,v,rPos)
                    findPos = True
                    break
                nowLevelPos>>=1
            if not findPos:
                self.posMapStash[len(posTree)-1-2].append((k,v,rPos))
        
        posList = []
        for i in range(1, 1+len(tempPosMap)//2):
            posList.append((i,(tempPosMap[2*i-1],tempPosMap[2*i])))
        return posList
    
    def initialization(self, elementList):
        tempPosMap = {}
        """
        Write to valTree
        """
        for (k,v) in elementList: # (virtualAddr, val): addr is from [1,N]
            rPos = random.randint(0,2**(len(self.valTree)-1)-1)
            tempPosMap[k] = rPos
            nowLevelPos = rPos
            findPos = False
            for level in range(self.valTreeMaxLevelID,-1,-1):
                if PathORAMRecursive.emptyElement in self.valTree[level][nowLevelPos]:
                    self.valTree[level][nowLevelPos][self.valTree[level][nowLevelPos].index(PathORAMRecursive.emptyElement)] = (k,v,rPos)
                    findPos = True
                    break
                nowLevelPos>>=1
            if not findPos:
                self.valStash.append((k,v,rPos))
        posList = []
        for i in range(1, 1+len(tempPosMap)//2):
            posList.append((i,(tempPosMap[2*i-1],tempPosMap[2*i]))) # left: even; right: odd
        for treeInd in range(len(self.posMapTree)-1,-1,-1):
            posList = self.writePosTree(posList,self.posMapTree[treeInd])
        for (_, tmpPos) in posList:
            self.localPosMap.append(tmpPos)

        self.localPosMapStorageInKB = (len(self.localPosMap)<<1)*math.ceil(self.firstPosTreeMaxLevelID/8)/(2**10) # save (len(self.localPosMap)<<1) locations, each with self.firstPosTreeMaxLevelID-bit
        self.localStashStorageInKB = (16+16+math.ceil((len(self.valTree)-1)/8))*len(self.valStash) # First compute the valTree
        currentPosBit = self.firstPosTreeMaxLevelID
        for i in range(len(self.posMapStash)):
            self.localStashStorageInKB += (16+math.ceil((currentPosBit+1)/8)+math.ceil((currentPosBit+1)/8)+math.ceil(currentPosBit/8))*len(self.posMapStash[i]) # (k,(nextPos,nextPos),pos): (16-byte, (log2(NextN),log2(NextN)), log2(NowN))
            currentPosBit += 1
        self.localStashStorageInKB /= (2**10)


    def readPosToStash(self, k, vLoc, posTree, posStash, currentTreePath, updatedNextTreePath):
        nextPath = -1
        updatedNextPath = -1
        for i in range(len(posStash)):
            if k==posStash[i][0]:
                nextPath = posStash[i][1][vLoc]
                updatedNextPath = random.randint(0,(len(posTree[len(posTree)-1])<<1)-1)
                if vLoc==0:
                    posStash[i] = (posStash[i][0],(updatedNextPath,posStash[i][1][1]),updatedNextTreePath)
                else:
                    posStash[i] = (posStash[i][0],(posStash[i][1][0],updatedNextPath),updatedNextTreePath)
                break
        nowLevelPos = currentTreePath
        for level in range(len(posTree)-1,-1,-1):
            for j in range(len(posTree[level][nowLevelPos])):
                if posTree[level][nowLevelPos][j]!=PathORAMRecursive.emptyPos:
                    if k==posTree[level][nowLevelPos][j][0]:
                        nextPath = posTree[level][nowLevelPos][j][1][vLoc] 
                        updatedNextPath = random.randint(0,(len(posTree[len(posTree)-1])<<1)-1)
                        if vLoc==0:
                            posStash.append((posTree[level][nowLevelPos][j][0],(updatedNextPath,posTree[level][nowLevelPos][j][1][1]),updatedNextTreePath))
                        else:
                            posStash.append((posTree[level][nowLevelPos][j][0],(posTree[level][nowLevelPos][j][1][0],updatedNextPath),updatedNextTreePath))
                    else:
                        posStash.append(posTree[level][nowLevelPos][j])
            nowLevelPos>>=1
        return nextPath, updatedNextPath

    def readValToStash(self, k, modV, op, currentTreePath,updatedNextTreePath):
        resAddrEle = (-1, get_random_bytes(16))
        for i in range(len(self.valStash)):
            if k==self.valStash[i][0]:
                resAddrEle = (self.valStash[i][0],self.valStash[i][1])
                if op=="write":
                    self.valStash[i]=(k,modV,updatedNextTreePath)
                else:
                    self.valStash[i]=(k,self.valStash[i][1],updatedNextTreePath)
                break
        nowLevelPos = currentTreePath
        """
        Read to stash
        """
        for level in range(len(self.valTree)-1,-1,-1):
            for j in range(len(self.valTree[level][nowLevelPos])):
                if self.valTree[level][nowLevelPos][j]!=PathORAMRecursive.emptyElement:
                    if k==self.valTree[level][nowLevelPos][j][0]:
                        resAddrEle = (self.valTree[level][nowLevelPos][j][0],self.valTree[level][nowLevelPos][j][1])
                        if op=="write":
                            self.valStash.append((k,modV,updatedNextTreePath))
                        else:    
                            self.valStash.append((k,self.valTree[level][nowLevelPos][j][1],updatedNextTreePath))
                    else:
                        self.valStash.append(self.valTree[level][nowLevelPos][j])
            nowLevelPos>>=1
        return resAddrEle

    def evictPosMap(self, evictStash, evictTree, evictPath):
        """
        Construct the evict path
        """
        tempStash = []
        writePath = [[PathORAMRecursive.emptyPos for _ in range(self.Z)] for _ in range(len(evictTree))]
        for i in range(len(evictStash)):
            writeFlag = False
            sharedLevel = findSharedLevel(evictStash[i][2],evictPath,len(evictTree)-1)
            for j in range(sharedLevel,-1,-1):
                if PathORAMRecursive.emptyPos in writePath[j]:
                    writePath[j][writePath[j].index(PathORAMRecursive.emptyPos)]=evictStash[i]
                    writeFlag = True
                    break
            if not writeFlag:
                tempStash.append(evictStash[i])
        """
        Write back
        """
        nowLevelPos = evictPath
        for level in range(len(evictTree)-1,-1,-1):
            evictTree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1
        return tempStash

    def evictVal(self, evictPath):
        """
        Construct the evict path
        """
        tempStash = []
        writePath = [[PathORAMRecursive.emptyElement for _ in range(self.Z)] for _ in range(len(self.valTree))]
        for i in range(len(self.valStash)):
            writeFlag = False
            sharedLevel = findSharedLevel(self.valStash[i][2],evictPath,len(self.valTree)-1)
            for j in range(sharedLevel,-1,-1):
                if PathORAMRecursive.emptyElement in writePath[j]:
                    writePath[j][writePath[j].index(PathORAMRecursive.emptyElement)]=self.valStash[i]
                    writeFlag = True
                    break
            if not writeFlag:
                tempStash.append(self.valStash[i])
        """
        Write back
        """
        nowLevelPos = evictPath
        for level in range(len(self.valTree)-1,-1,-1):
            self.valTree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1
        self.valStash = tempStash

    def access(self, k, modV, op):
        yList = [k] # k is range from {1,2,3,...}
        for _ in range(self.valTreeMaxLevelID-self.firstPosTreeMaxLevelID+1):
            yList.insert(0,math.ceil(yList[0]/2))
        posList = []
        nextTreePath = self.localPosMap[yList[0]-1][(yList[1]+1)%2]
        updatedNextTreePath = random.randint(0,(len(self.localPosMap))-1)
        if (yList[1]+1)%2==0:
            self.localPosMap[yList[0]-1] = (updatedNextTreePath, self.localPosMap[yList[0]-1][1])
        else:
            self.localPosMap[yList[0]-1] =(self.localPosMap[yList[0]-1][0], updatedNextTreePath)
        posList.append(nextTreePath)
        for i in range(2,len(yList)):
            vLoc = (yList[i]+1)%2
            nextTreePath, updatedNextTreePath = self.readPosToStash(yList[i-1],vLoc,self.posMapTree[i-2],self.posMapStash[i-2],nextTreePath,updatedNextTreePath)
            posList.append(nextTreePath)
        result = self.readValToStash(yList[len(yList)-1],modV,op,nextTreePath,updatedNextTreePath)
        
        for i in range(2,len(yList)):
            self.posMapStash[i-2] = self.evictPosMap(self.posMapStash[i-2],self.posMapTree[i-2],posList[i-2])
        self.evictVal(posList[len(posList)-1])


        # (k,v,leafNum): (16-byte, 16-byte, log2(N))
        # (k,(nextPos,nextPos),pos): (16-byte, (log2(NextN),log2(NextN)), log2(NowN))  
        self.localPosMapStorageInKB = (len(self.localPosMap)<<1)*math.ceil(self.firstPosTreeMaxLevelID/8)/(2**10) # save (len(self.localPosMap)<<1) locations, each with self.firstPosTreeMaxLevelID-bit
        self.localStashStorageInKB = (16+16+math.ceil((len(self.valTree)-1)/8))*len(self.valStash) # First compute the valTree
        currentPosBit = self.firstPosTreeMaxLevelID
        for i in range(len(self.posMapStash)):
            self.localStashStorageInKB += (16+math.ceil((currentPosBit+1)/8)+math.ceil((currentPosBit+1)/8)+math.ceil(currentPosBit/8))*len(self.posMapStash[i]) # (k,(nextPos,nextPos),pos): (16-byte, (log2(NextN),log2(NextN)), log2(NowN))
            currentPosBit += 1
        self.localStashStorageInKB /= (2**10)
        self.bandwidthInKB = self.Z*len(self.valTree)*(16+16+math.ceil((len(self.valTree)-1)/8))
        currentPosBit = self.firstPosTreeMaxLevelID
        for i in range(len(self.posMapTree)):
            self.bandwidthInKB += self.Z*len(self.posMapTree[i])*(16+math.ceil((currentPosBit+1)/8)+math.ceil((currentPosBit+1)/8)+math.ceil(currentPosBit/8))# (k,(nextPos,nextPos),pos): (16-byte, (log2(NextN),log2(NextN)), log2(NowN))
            currentPosBit += 1
        self.bandwidthInKB *= 2
        self.bandwidthInKB /= (2**10)
        return result
    
if __name__=="__main__":
    N = 2**30
    elementList = []
    for i in range(N):
        elementList.append((i+1,get_random_bytes(16)))
    prORAM = PathORAMRecursive(N, 2)
    prORAM.initialization(elementList)
    #print(prORAM.localPosMap)
    #print(prORAM.posMapTree)
    accessTimes = 2**10
    opS = ["read","write"]
    beginTime = time.time()
    for i in range(accessTimes):
        modV = get_random_bytes(16)
        searchInd = random.randint(0,N-1)
        op = random.choice(opS)
        result = prORAM.access(elementList[searchInd][0],modV,op)
        assert result==elementList[searchInd]
        if op=="write":
            elementList[searchInd]=(elementList[searchInd][0],modV)
        if i%1000==0:
            update_loading_bar(i/accessTimes)
    endTime = time.time()
    #print(len(prORAM.localPosMap))
    print("\nTime consumes {} ms".format(1000*(endTime-beginTime)/accessTimes))
    print("Position map consumes {} KB".format(prORAM.localPosMapStorageInKB))
    print("Stash consumes {} KB".format(prORAM.localStashStorageInKB))
    print("Bandwidth is {} KB".format(prORAM.bandwidthInKB))

