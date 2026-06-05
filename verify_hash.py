import bcrypt
h = b'$2b$12$j0ChPrsj4P85Wnu8ErSYTu1Dk24m8LGmoe6Jz40sqatU5UtHj2vae'
print('Match Admin@123:', bcrypt.checkpw(b'Admin@123', h))
