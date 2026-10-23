from caliper.application.auth import hash_password, verify_password


def test_password_hash_verifies_without_retaining_plaintext():
    raw_password = "a test-only administrator password"
    encoded = hash_password(raw_password)
    assert encoded != raw_password
    assert encoded.startswith("$argon2id$")
    assert verify_password(raw_password, encoded)
    assert not verify_password("incorrect password", encoded)
