import hashlib as hl #hash library
import json #used for encoding objects as strings

#__all__ = ['hash_string_256', 'hash_block']

def hash_string_256(string):
    return hl.sha256(string).hexdigest()


def hash_block(block):
    #json.dumps creates a json formatted string, encode used for UTF-8
    #sort_keys is used because dictionaries are unordered and could cause a problem with hashes if  the order suddenly changes
    hashable_block = block.__dict__.copy() #copy is used to get a new dictionary so that changes won't affect the old dictionary - hashed stay the same
    hashable_block['transactions'] = [tx.to_ordered_dict() for tx in hashable_block['transactions']]
    return hash_string_256(json.dumps(hashable_block, sort_keys=True).encode())