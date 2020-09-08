import hashlib

def authorize(gets,posts,token,secret_key):
    try:
        all = []
        all.extend(gets+posts)
        all.append(secret_key)
        all.sort()
        all_str = ''.join(all)
        #print("all_str:",all_str)
        encoded = hashlib.md5(all_str.encode()).hexdigest()
        #print("encoded:",encoded)
        return token == encoded
    except:
        return False
