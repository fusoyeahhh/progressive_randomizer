import random
import math

def shuffle(collection):
    return random.sample(list(collection), k=len(collection))

def shuffle_idx(n):
    return random.sample(range(n), k=n)

def choice_without_replacement(pool, k=1):
    # Probably slow
    idx = list(range(len(pool)))
    random.shuffle(idx)
    return [pool[i] for i in idx[:k]]

# TODO: a lot of this could be replaced with a discrete beta
def triangle(a, b, c=0, n=2):
    return c + sum([random.randint(a, b) for _ in range(n)])

def match_n(n, m=0):
    return random.randint(0, n) == m

def accum_n(n, b, a=0, init=0):
    while match_n(n):
        init += random.randint(a, b)
    return init

def random_prob(p=0.5):
    return random.uniform(0, 1) < p

def poisson(l=1):
    k, p = 0, 1
    while p > math.exp(-l):
        k += 1
        p *= random.uniform(0, 1)

    return k - 1

def discrete_beta(n=1, mode=1, inv_width=1):
    # FIXME: disallow the mode = n problem
    alpha = mode / n * (2 * inv_width - 2) + 1
    beta = (1 - mode / n) * (2 * inv_width - 2) + 1
    return int(n * random.betavariate(alpha, beta)) % n
