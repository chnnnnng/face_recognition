FROM chng/face_recognition_server:v2
COPY . /face_bk
CMD ["sh","/start.sh"]

