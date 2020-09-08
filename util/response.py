from flask import jsonify

class response:
    status = ''
    msg = ''
    data = ''


    def succeed(self):
        self.status = 'ok'
        return self


    def error(self):
        self.status = 'error'
        return self


    def message(self,msg):
        self.msg = msg and msg
        return self


    def setdata(self,data):
        self.data = data and data
        return self


    def make(self):
        return jsonify({'status':self.status,'msg':self.msg,'data':self.data})