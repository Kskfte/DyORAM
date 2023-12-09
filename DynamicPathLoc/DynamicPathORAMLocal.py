import random
import math
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from putils import dynamicFindSharedLevel,update_loading_bar,reverseBit,revLexCompare,remapPos
import time
import copy

"""
An element = (key, value) = (int, 16-byte)
Fix the key (or addr) to 16-byte
"""
class PathORAM:

    emptyElement = (-1,bytes(16))
    def __init__(self, N) -> None:
        self.N = N # InitSize
        self.Z = 2
        """
        Storing in Client
        """
        self.currentMaxLevelID = math.ceil(math.log2(N))-1 # Level: 0,1,...,self.currentMaxLevelID
        self.currentMaxLeafID = reverseBit(self.N-1-2**(self.currentMaxLevelID),self.currentMaxLevelID)
        self.seqMaxLeafID = self.N-1-2**(self.currentMaxLevelID)
        self.posMap = {} # (k, leafID, leafLevel)
        self.stash = []
        """
        Storing in Server
        """
        self.Tree = [[[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(2**i)] for i in range(self.currentMaxLevelID+1)]
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
        self.posMapStorageInKB = 0 #len(self.posMap)*(16+self.currentMaxLevelID//8)/(2**10)
        self.stashStorageInKB = 0 #len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB = 0 #32*2*pORAM.Z*(pORAM.currentMaxLevelID+1)/(2**10)

    def initialization(self, elementList):
        for (k,v) in elementList:
            nowLeaf,nowLevel = remapPos(self.currentMaxLeafID,self.currentMaxLevelID)
            self.posMap[k] = nowLeaf,nowLevel
            findPos = False
            for level in range(nowLevel,-1,-1):
                if PathORAM.emptyElement in self.Tree[level][nowLeaf]:
                    self.Tree[level][nowLeaf][self.Tree[level][nowLeaf].index(PathORAM.emptyElement)] = (k,v)
                    findPos = True
                    break
                nowLeaf>>=1
            if not findPos:
                self.stash.append((k,v))
        
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
    
    def access(self, k, modV, op):
        if op=="read":
            return self.search(k)
        else:
            return self.modify(k,modV)
    
    def search(self, k):
        kLeaf,kLevel = self.posMap[k]
        if kLevel>=self.currentMaxLevelID:
            kLeaf >>= (kLevel-self.currentMaxLevelID)
            kLevel -= (kLevel-self.currentMaxLevelID)
            if not revLexCompare(self.currentMaxLevelID,kLeaf,self.currentMaxLeafID):
                kLevel -= 1
                kLeaf >>= 1
        self.posMap[k] = remapPos(self.currentMaxLeafID,self.currentMaxLevelID)
        
        result = PathORAM.emptyElement
        foundFlag = False
        writeFlag = False
        tempStash = []
        nowLevelPos = kLeaf
        """
        Read to stash
        """
        for level in range(kLevel,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        """
        Construct the evict path
        """
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(kLevel+1)]
        for i in range(len(self.stash)):
            writeFlag = False
            if not foundFlag and self.stash[i][0]==k:
                result=self.stash[i]
                foundFlag=True
            sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(kLeaf,kLevel))
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
        nowLevelPos = kLeaf
        for level in range(kLevel,-1,-1):
            self.Tree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1

        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(kLevel+1)/(2**10)

        return result

    def modify(self, k, modV):
        kLeaf,kLevel = self.posMap[k]
        if kLevel>=self.currentMaxLevelID:
            kLeaf >>= (kLevel-self.currentMaxLevelID)
            kLevel -= (kLevel-self.currentMaxLevelID)
            if not revLexCompare(self.currentMaxLevelID,kLeaf,self.currentMaxLeafID):
                kLevel -= 1
                kLeaf >>= 1

        self.posMap[k] = remapPos(self.currentMaxLeafID,self.currentMaxLevelID)
        
        result = PathORAM.emptyElement
        foundFlag = False
        writeFlag = False
        tempStash = []
        nowLevelPos = kLeaf
        """
        Read to stash
        """
        for level in range(kLevel,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        #print(self.stash)
        """
        Construct the evict path
        """
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(kLevel+1)]
        for i in range(len(self.stash)):
            writeFlag = False
            if not foundFlag and self.stash[i][0]==k:
                result=self.stash[i]
                self.stash[i]=(k,modV)
                foundFlag=True
            sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(kLeaf,kLevel))
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
        nowLevelPos = kLeaf
        for level in range(kLevel,-1,-1):
            self.Tree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1

        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += 2*(16+16)*self.Z*(kLevel+1)/(2**10)

        return result

    def add(self, k, addV):
        if self.currentMaxLeafID==2**self.currentMaxLevelID-1:
            self.currentMaxLeafID = 0
            self.seqMaxLeafID = 0
            self.currentMaxLevelID += 1
            if len(self.Tree)<=self.currentMaxLevelID:
                self.Tree.append([[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(2**self.currentMaxLevelID)])
        else:
            self.seqMaxLeafID += 1
            self.currentMaxLeafID = reverseBit(self.seqMaxLeafID,self.currentMaxLevelID)
        self.posMap[k] = remapPos(self.currentMaxLeafID,self.currentMaxLevelID)
        
        #print("Add:{}".format(self.currentMaxLeafID))

        writeFlag = False
        tempStash = []
        nowLevelPos = self.currentMaxLeafID>>1
        """
        Read to stash
        """
        self.stash.append((k,addV))
        for level in range(self.currentMaxLevelID-1,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        """
        Construct the evict path
        """
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(self.currentMaxLevelID+1)]
        for i in range(len(self.stash)):
            sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(self.currentMaxLeafID,self.currentMaxLevelID))
            if sharedLevel==self.currentMaxLevelID-1 and sharedLevel==self.posMap[self.stash[i][0]][1]:
                if self.currentMaxLeafID&1==0:
                    self.posMap[self.stash[i][0]] = random.choice([self.posMap[self.stash[i][0]],(self.currentMaxLeafID,self.currentMaxLevelID)])
                    sharedLevel=self.posMap[self.stash[i][0]][1]
                else:
                    self.posMap[self.stash[i][0]] = (self.currentMaxLeafID,self.currentMaxLevelID)
                    sharedLevel=self.posMap[self.stash[i][0]][1]
            
            writeFlag = False
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
        nowLevelPos = self.currentMaxLeafID
        for level in range(self.currentMaxLevelID,-1,-1):
            self.Tree[level][nowLevelPos]=writePath[level]
            nowLevelPos>>=1
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
        self.bandwidthInKB += (16+16)*self.Z*((self.currentMaxLevelID<<1)-1)/(2**10)
    
    def delete(self, k):
        kLeaf,kLevel = self.posMap[k]
        if kLevel>=self.currentMaxLevelID:
            kLeaf >>= (kLevel-self.currentMaxLevelID)
            kLevel -= (kLevel-self.currentMaxLevelID)
            if not revLexCompare(self.currentMaxLevelID,kLeaf,self.currentMaxLeafID):
                kLevel -= 1
                kLeaf >>= 1
        nowLevelPos = kLeaf
        foundFlag = False
        writeFlag = False
        tempStash = []
        """
        Read to stash
        """
        for level in range(kLevel,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1

        if not (kLeaf==self.currentMaxLeafID and kLevel==self.currentMaxLevelID):
            for ele in self.Tree[self.currentMaxLevelID][self.currentMaxLeafID]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)

            
            """
            Construct the evict path
            """
            writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(kLevel+1)]
            for i in range(len(self.stash)):
                writeFlag = False
                if not foundFlag and self.stash[i][0]==k:
                    foundFlag=True
                    self.posMap.pop(self.stash[i][0])
                    continue
                #if self.posMap[self.stash[i][0]]==(self.currentMaxLeafID,self.currentMaxLevelID):
                #    self.posMap[self.stash[i][0]]=(self.currentMaxLeafID>>1,self.currentMaxLevelID-1)
                sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(kLeaf,kLevel))
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
            nowLevelPos = kLeaf
            for level in range(kLevel,-1,-1):
                self.Tree[level][nowLevelPos]=writePath[level]
                nowLevelPos>>=1
            self.Tree[self.currentMaxLevelID][self.currentMaxLeafID] = [PathORAM.emptyElement for _ in range(self.Z)]

            """
            Overhead
            """
            self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
            self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
            self.bandwidthInKB += (2*(16+16)*self.Z*(kLevel+1)+(16+16)*self.Z)/(2**10)

        else:
            """
            Construct the evict path
            """
            foundFlag = False
            writeFlag = False
            tempStash = []
            writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(kLevel)]
            for i in range(len(self.stash)):
                writeFlag = False
                if not foundFlag and self.stash[i][0]==k:
                    foundFlag=True
                    self.posMap.pop(self.stash[i][0])
                    continue
                #if self.posMap[self.stash[i][0]]==(self.currentMaxLeafID,self.currentMaxLevelID):
                #    self.posMap[self.stash[i][0]]=(self.currentMaxLeafID>>1,self.currentMaxLevelID-1)
                sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(self.currentMaxLeafID>>1,self.currentMaxLevelID-1))
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
            nowLevelPos = self.currentMaxLeafID>>1
            for level in range(self.currentMaxLevelID-1,-1,-1):
                self.Tree[level][nowLevelPos]=writePath[level]
                nowLevelPos>>=1
            self.Tree[self.currentMaxLevelID][self.currentMaxLeafID] = [PathORAM.emptyElement for _ in range(self.Z)]

            """
            Overhead
            """
            self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
            self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)
            self.bandwidthInKB += (((kLevel<<1)+1)*(16+16)*self.Z)/(2**10)

        #for k in self.posMap.keys():
        #    if self.posMap[k]==(self.currentMaxLeafID,self.currentMaxLevelID):
        #        self.posMap[k]=(self.currentMaxLeafID>>1,self.currentMaxLevelID-1)

        if self.currentMaxLeafID==0:
            self.currentMaxLevelID -= 1
            self.currentMaxLeafID = 2**self.currentMaxLevelID-1
            self.seqMaxLeafID = self.currentMaxLeafID
        else:
            self.seqMaxLeafID -= 1
            self.currentMaxLeafID = reverseBit(self.seqMaxLeafID,self.currentMaxLevelID)

    def delete2222(self, k):
        kLeaf,kLevel = self.posMap[k]
        
        foundFlag = False
        writeFlag = False
        tempStash = []
        nowLevelPos = kLeaf
        """
        Read to stash
        """
        for level in range(kLevel,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1
        """
        Construct the evict path
        """
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(kLevel+1)]
        for i in range(len(self.stash)):
            writeFlag = False
            if not foundFlag and self.stash[i][0]==k:
                foundFlag=True
                self.posMap.pop(self.stash[i][0])
                continue
            sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(kLeaf,kLevel))
            for j in range(sharedLevel,-1,-1):
                if PathORAM.emptyElement in writePath[j]:
                    writePath[j][writePath[j].index(PathORAM.emptyElement)]=self.stash[i]
                    writeFlag = True
                    break
            if not writeFlag:
                tempStash.append(self.stash[i])
        self.stash = copy.deepcopy(tempStash)
        """
        Write back
        """
        nowLevelPos = kLeaf
        for level in range(kLevel,-1,-1):
            self.Tree[level][nowLevelPos]=copy.deepcopy(writePath[level])
            nowLevelPos>>=1


        ################################################################################################
        ################################################################################################
        writeFlag = False
        tempStash = []
        """
        Read to stash
        """
        nowLevelPos = self.currentMaxLeafID
        for level in range(self.currentMaxLevelID,-1,-1):
            for ele in self.Tree[level][nowLevelPos]:
                if ele!=PathORAM.emptyElement:
                    self.stash.append(ele)
            nowLevelPos>>=1

        """
        Construct the evict path
        """
        writePath = [[PathORAM.emptyElement for _ in range(self.Z)] for _ in range(self.currentMaxLevelID)]
        for i in range(len(self.stash)):
            writeFlag = False
            if self.posMap[self.stash[i][0]]==(self.currentMaxLeafID,self.currentMaxLevelID):
                self.posMap[self.stash[i][0]]=(self.currentMaxLeafID>>1,self.currentMaxLevelID-1)
            sharedLevel = dynamicFindSharedLevel(self.posMap[self.stash[i][0]],(self.currentMaxLeafID>>1,self.currentMaxLevelID-1))
            for j in range(sharedLevel,-1,-1):
                if PathORAM.emptyElement in writePath[j]:
                    writePath[j][writePath[j].index(PathORAM.emptyElement)]=self.stash[i]
                    writeFlag = True
                    break
            if not writeFlag:
                tempStash.append(self.stash[i])
        self.stash = copy.deepcopy(tempStash)
        """
        Write back
        """
        nowLevelPos = self.currentMaxLeafID>>1
        for level in range(self.currentMaxLevelID-1,-1,-1):
            self.Tree[level][nowLevelPos]=copy.deepcopy(writePath[level])
            nowLevelPos>>=1
        self.Tree[self.currentMaxLevelID][self.currentMaxLeafID] = [PathORAM.emptyElement for _ in range(self.Z)]
    
        """
        Overhead
        """
        self.posMapStorageInKB = len(self.posMap)*(16+math.ceil((len(self.Tree)-1)/8)+math.ceil(math.log2(len(self.Tree)-1)/8))/(2**10)
        self.stashStorageInKB = len(self.stash)*(16+16)/(2**10)

        self.bandwidthInKB += (2*(16+16)*self.Z*(kLevel+1)+2*(16+16)*self.Z*((self.currentMaxLevelID<<1)-1))/(2**10)


        if self.currentMaxLeafID==0:
            self.currentMaxLevelID -= 1
            self.currentMaxLeafID = 2**self.currentMaxLevelID-1
            self.seqMaxLeafID = self.currentMaxLeafID
        else:
            self.seqMaxLeafID -= 1
            self.currentMaxLeafID = reverseBit(self.seqMaxLeafID,self.currentMaxLevelID)


if __name__=="__main__":
    N = 2**20
    elementList = []
    for i in range(N):
        kv = (i+1,get_random_bytes(16))
        elementList.append(kv)
    pORAM = PathORAM(N)
    pORAM.initialization(elementList)

    
    accessTimes = math.ceil(math.sqrt(N))
    newK = N+1
    opList = ["access","add","delete"]
    opProbab = [0.5, 0.4, 0.1]

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
    
    
