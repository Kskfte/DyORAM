import random
import math
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from utils import findSharedLevel
from utils import update_loading_bar
import time

"""
An element = (key, value) = (int, 16-byte)
Fix the key (or addr) to 16-byte
"""
class PathORAM:

    emptyElement = (-1,bytes(16))
    def __init__(self, N) -> None:
        self.N = N # InitSize
        self.M = N # CurrentSize
        self.Z = 2
        """
        Storing in Client
        """
        self.posMap = {}
        self.stash = []
        """
        Storing in Server
        """
        self.treeDepth = math.ceil(math.log2(N)) # 0, 1, ..., self.treeDepth
        self.Tree = [[[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(2**i)] for i in range(self.treeDepth+1)]
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
        self.posMapStorageInKB = 0 #len(self.posMap)*(16+self.treeDepth//8)/(2**10)
        self.stashStorageInKB = 0 #len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 0 #32*2*pORAM.Z*(pORAM.treeDepth+1)/(2**10)

    def initialization(self, elementList):
        for (k,v) in elementList:
            rPos = random.randint(0,2**self.treeDepth-1)
            self.posMap[k] = rPos
            nowLevelPos = rPos
            findPos = False
            for level in range(self.treeDepth,-1,-1):
                if PathORAM.emptyElement in self.Tree[level][nowLevelPos]:
                    self.Tree[level][nowLevelPos][self.Tree[level][nowLevelPos].index(PathORAM.emptyElement)] = (k,v)
                    findPos = True
                    break
                nowLevelPos>>=1
            if not findPos:
                self.stash.append((k,v))
        
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)

    def readAndEvictOnePath(self, leafInd, op, k, modV):
        result = PathORAM.emptyElement
        nowLevelPos = leafInd
        foundFlag = False
        writeFlag = False
        tempStash = []
        """
        Read to stash
        """
        for level in range(self.treeDepth,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        """
        Construct the evict path
        """
        writeTimes = 0
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(self.treeDepth+1)]
        for i in range(len(self.stash)):
            if writeTimes==self.Z*(self.treeDepth+1):
                tempStash.extend(self.stash[i:])
                break
            writeFlag = False
            if op=="search":
                if not foundFlag and self.stash[i][0]==k:
                    result=self.stash[i]
                    foundFlag=True
            elif op=="modify":
                if not foundFlag and self.stash[i][0]==k:
                    result=self.stash[i]
                    self.stash[i]=(k,modV)
                    foundFlag=True
            elif op=="add":
                pass
            else: # delete
                if not foundFlag and self.stash[i][0]==k:
                    foundFlag=True
                    continue
            sharedLevel = findSharedLevel(self.posMap[self.stash[i][0]],leafInd,self.treeDepth)
            for j in range(sharedLevel,-1,-1):
                if PathORAM.emptyElement in writePath[j]:
                    writePath[j][writePath[j].index(PathORAM.emptyElement)]=self.stash[i]
                    writeFlag = True
                    break
            if not writeFlag:
                tempStash.append(self.stash[i])
        self.stash = tempStash
        """
        Write back
        """
        nowLevelPos = leafInd
        for level in range(self.treeDepth,-1,-1):
            self.Tree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1

        return result

    def access(self, k, modV, op):
        if op=="read":
            return self.search(k)
        else:
            return self.modify(k,modV)
    
    def search(self, k):
        kPos = self.posMap[k]
        self.posMap[k] = random.randint(0,2**self.treeDepth-1)
        result = self.readAndEvictOnePath(kPos,"search",k,bytes(16))
            
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 2*(16+16)*self.Z*len(self.Tree)/(2**10)

        return result

    def modify(self, k, modV):
        kPos = self.posMap[k]
        self.posMap[k] = random.randint(0,2**self.treeDepth-1)
        result = self.readAndEvictOnePath(kPos,"modify",k,modV)
        
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 2*(16+16)*self.Z*len(self.Tree)/(2**10)

        return result

    def add(self, k, addV):
        self.stash.append((k,addV))
        self.posMap[k] = random.randint(0,2**self.treeDepth-1)
        self.readAndEvictOnePath(random.randint(0,2**self.treeDepth-1),"add",bytes(16),bytes(16)) 

        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 2*(16+16)*self.Z*len(self.Tree)/(2**10)
    
    def delete(self, k):
        kPos = self.posMap[k]
        self.posMap.pop(k)
        self.readAndEvictOnePath(kPos,"delete",k,bytes(16)) 
    
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 2*(16+16)*self.Z*len(self.Tree)/(2**10)


if __name__=="__main__":
    N = 2**10
    elementList = []
    for i in range(N):
        elementList.append((i+1,get_random_bytes(16)))
    pORAM = PathORAM(N)
    pORAM.initialization(elementList)
    accessTimes = 2**10
    opS = ["read","write"]

    beginTime = time.time()
    for i in range(accessTimes):
        modV = get_random_bytes(16)
        searchInd = random.randint(0,N-1)
        op = random.choice(opS)
        assert pORAM.access(elementList[searchInd][0],modV,op)==elementList[searchInd]
        if op=="write":
            elementList[searchInd] = (elementList[searchInd][0],modV)
        if i%1000==0:
            update_loading_bar(i/accessTimes)
    endTime = time.time()
    print("\nTime consumes {} ms".format(1000*(endTime-beginTime)/accessTimes))
    print("Position map consumes {} KB".format(pORAM.posMapStorageInKB))
    print("Stash consumes {} KB".format(pORAM.stashStorageInKB))
    print("Bandwidth is {} KB".format(pORAM.bandwidthInKB))

    
