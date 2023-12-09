import random
import math
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from putils import staticFindSharedLevel,update_loading_bar
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
        self.maxLevelID = math.ceil(math.log2(N))-1 # 0, 1, ..., self.maxLevelID maxLevelID
        self.stThreshold = self.Z*(self.maxLevelID+1)
        self.Tree = [[[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(2**i)] for i in range(self.maxLevelID+1)]
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
        self.posMapStorageInKB = 0 #len(self.posMap)*(16+self.maxLevelID//8)/(2**10)
        self.stashStorageInKB = 0 #len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 0 #32*2*pORAM.Z*(pORAM.maxLevelID+1)/(2**10)

    def initialization(self, elementList):
        for (k,v) in elementList:
            rPos = random.randint(0,2**self.maxLevelID-1)
            self.posMap[k] = rPos
            nowLevelPos = rPos
            findPos = False
            for level in range(self.maxLevelID,-1,-1):
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
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)

    def rebuild(self, expandOrShrink): # expand: 1; shrink: -1
        for lev in range(self.maxLevelID,-1,-1):
            for bucket in self.Tree[lev]:
                for ele in bucket:
                    if ele!=PathORAM.emptyElement:
                        self.stash.append(ele)
        
        
        self.maxLevelID += expandOrShrink
        self.Tree = [[[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(2**i)] for i in range(self.maxLevelID+1)]
        self.posMap = {}
        self.N = len(self.stash)
        self.M = N
        self.stThreshold = self.Z*(self.maxLevelID+1)

        tempStash = []
        for (k,v) in self.stash:
            rPos = random.randint(0,2**self.maxLevelID-1)
            self.posMap[k] = rPos
            nowLevelPos = rPos
            findPos = False
            for level in range(self.maxLevelID,-1,-1):
                if PathORAM.emptyElement in self.Tree[level][nowLevelPos]:
                    self.Tree[level][nowLevelPos][self.Tree[level][nowLevelPos].index(PathORAM.emptyElement)] = (k,v)
                    findPos = True
                    break
                nowLevelPos>>=1
            if not findPos:
                tempStash.append((k,v))
        self.stash = tempStash


        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        if expandOrShrink==1:
            self.bandwidthInKB += (16+16)*self.Z*(2**self.maxLevelID-1+2**(self.maxLevelID+1)-1)/(2**10)
        else:
            self.bandwidthInKB += (16+16)*self.Z*(2**(self.maxLevelID+2)-1+2**(self.maxLevelID+1)-1)/(2**10)

    def readAndEvictOnePath(self, leafInd, op, k, modV):
        result = PathORAM.emptyElement
        nowLevelPos = leafInd
        foundFlag = False
        writeFlag = False
        tempStash = []
        """
        Read to stash
        """
        for level in range(self.maxLevelID,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        """
        Construct the evict path
        """
        writeTimes = 0
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(self.maxLevelID+1)]
        for i in range(len(self.stash)):
            writeFlag = False
            if op=="search":
                if not foundFlag and self.stash[i][0]==k:
                    result=self.stash[i]
                    foundFlag=True
                if foundFlag and writeTimes==self.Z*(self.maxLevelID+1):
                    tempStash.extend(self.stash[i:])
                    break
            elif op=="modify":
                if not foundFlag and self.stash[i][0]==k:
                    result=self.stash[i]
                    self.stash[i]=(k,modV)
                    foundFlag=True
                if foundFlag and writeTimes==self.Z*(self.maxLevelID+1):
                    tempStash.extend(self.stash[i:])
                    break
            elif op=="add":
                if writeTimes==self.Z*(self.maxLevelID+1):
                    tempStash.extend(self.stash[i:])
                    break
            else:
                if not foundFlag and self.stash[i][0]==k:
                    foundFlag=True
                    if writeTimes==self.Z*(self.maxLevelID+1):
                        if i+1<len(self.stash):
                            tempStash.extend(self.stash[i+1:])
                        break
                    else:
                        continue
                if foundFlag and writeTimes==self.Z*(self.maxLevelID+1):
                    tempStash.extend(self.stash[i:])
                    break
            sharedLevel = staticFindSharedLevel(self.posMap[self.stash[i][0]],leafInd,self.maxLevelID)
            for j in range(sharedLevel,-1,-1):
                if PathORAM.emptyElement in writePath[j]:
                    writePath[j][writePath[j].index(PathORAM.emptyElement)]=self.stash[i]
                    writeFlag = True
                    writeTimes += 1
                    break
            if not writeFlag:
                tempStash.append(self.stash[i])                
        self.stash = tempStash
        """
        Write back
        """
        nowLevelPos = leafInd
        for level in range(self.maxLevelID,-1,-1):
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
        self.posMap[k] = random.randint(0,2**self.maxLevelID-1)
        result = self.readAndEvictOnePath(kPos,"search",k,bytes(16))
            
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(self.maxLevelID+1)/(2**10)

        return result

    def modify(self, k, modV):
        kPos = self.posMap[k]
        self.posMap[k] = random.randint(0,2**self.maxLevelID-1)
        result = self.readAndEvictOnePath(kPos,"modify",k,modV)
        
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(self.maxLevelID+1)/(2**10)

        return result

    def add(self, k, addV):
        self.stash.append((k,addV))
        self.posMap[k] = random.randint(0,2**self.maxLevelID-1)
        self.readAndEvictOnePath(random.randint(0,2**self.maxLevelID-1),"add",bytes(16),bytes(16)) 
        self.M += 1

        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(self.maxLevelID+1)/(2**10)

        if len(self.stash)>=self.stThreshold:
            self.rebuild(1)
    
    def delete(self, k):
        kPos = self.posMap[k]
        self.posMap.pop(k)
        self.readAndEvictOnePath(kPos,"delete",k,bytes(16))
        self.M -= 1
    
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil(self.maxLevelID/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(self.maxLevelID+1)/(2**10)

        if abs(self.M)<=2**self.maxLevelID:
            self.rebuild(-1)

if __name__=="__main__":
    N = 2**10
    elementList = []
    for i in range(N):
        kv = (i+1,get_random_bytes(16))
        elementList.append(kv)
    pORAM = PathORAM(N)
    pORAM.initialization(elementList)

    
    accessTimes = N
    newK = N+1
    opList = ["access","add","delete"]
    opProbab = [0.5, 0.0, 0.5]

    beginTime = time.time()
    for i in range(accessTimes):
        op = random.choices(opList,opProbab)[0]
        if op=="access":
            modV = get_random_bytes(16)
            searchInd = random.randint(0,len(elementList)-1)
            wrop = random.choice(["read","write"])
            assert pORAM.access(elementList[searchInd][0],modV,wrop)==elementList[searchInd]
            if wrop=="write":
                elementList[searchInd] = (elementList[searchInd][0],modV)
        elif op=="add":
            newEle = newK, get_random_bytes(16)
            pORAM.add(newEle[0],newEle[1])
            elementList.append(newEle)
            newK += 1
        else: 
            deleteInd = random.randint(0,len(elementList)-1)
            pORAM.delete(elementList[deleteInd][0])
            elementList.remove(elementList[deleteInd])
        if i%1000==0:
            update_loading_bar(i/accessTimes)
    endTime = time.time()  

    print("\nTime consumes {} ms".format(1000*(endTime-beginTime)/accessTimes)) #/accessTimes
    print("Position map consumes {} KB".format(pORAM.posMapStorageInKB))
    print("Stash consumes {} KB".format(pORAM.stashStorageInKB))
    print("Bandwidth is {} KB".format(pORAM.bandwidthInKB/accessTimes))
    
    
