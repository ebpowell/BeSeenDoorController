from werkzeug.security import generate_password_hash, check_password_hash



def generate_hashed_password(plain_password):

    # 1. Generate the secure hash
    # (Werkzeug automatically generates a unique salt and combines it)
    hashed_password = generate_password_hash(plain_password)

    print(f"Hashed Password:\n{hashed_password}\n")
    return hashed_password


if __name__ == "__main__":
    plain_password = "randy1" 
    hashed_password = generate_hashed_password(plain_password)
    # 3. How to verify the password later (e.g., during login)
    is_correct = check_password_hash(hashed_password, plain_password)  # This should return True
    is_incorrect = check_password_hash(hashed_password, "WrongPassword!")

    print(f"Is correct password valid? {is_correct}")    # Returns True
    print(f"Is incorrect password valid? {is_incorrect}") # Returns False