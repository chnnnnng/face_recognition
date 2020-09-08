from redis import StrictRedis

class redis:

    _redis = None
    _prefix = ''


    def __init__(self, host='localhost', port=6379, password='', prefix='FRS:'):
        #连接redis
        self._redis = StrictRedis(host=host, port=port, db=0, password=password)
        self._prefix = prefix

    
    def _getFullKey(self,*key):
        return self._prefix+'/'.join(key)


    #redis.set('key1','key2',value='value') => set PREFIX:key1/key2 value
    def set(self,*key,value=''):
        if key and value:
            return self._redis.set(self._getFullKey(key),value)
        return False


    #redis.get('key1','key2') => get PREFIX:key1/key2
    def get(self,*key):
        if key:
            return self._redis.get(self._getFullKey(key))
        return None


    def getPicNum(self,faceid):
        if faceid:
            return self._redis.scard(self._getFullKey(faceid))
        return 0


    def getPics(self,faceid):
        if faceid:
            return self._redis.smembers(self._getFullKey(faceid))
        return 0


    def addPic(self,faceid,*pics):
        if faceid and pics:
            return self._redis.sadd(self._getFullKey(faceid),*pics)
        return False

    
    def delPic(self,faceid,*pics):
        if faceid and pics:
            return self._redis.srem(self._getFullKey(faceid),*pics)
        return False


    def addFace(self,faceid):
        if faceid:
            return not self._redis.exists(self._getFullKey(faceid))
        return False


    def delFace(self,faceid):
        if faceid:
            return self._redis.delete(self._getFullKey(faceid))
        return False