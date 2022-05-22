import random

def shuffle(collection):
    return random.sample(list(collection), k=len(collection))

def shuffle_idx(n):
    return random.sample(range(n), k=n)