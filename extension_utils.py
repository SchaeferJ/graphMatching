import csv
import math
from typing import Sequence
from copy import deepcopy
import numpy as np


def read_tsv(path: str, header: bool = True, as_dict: bool = False, delim: str = "\t") -> Sequence[Sequence[str]]:
    data = {} if as_dict else []
    uid = []
    with open(path, "r") as f:
        reader = csv.reader(f, delimiter=delim)
        if header:
            next(reader)
        for row in reader:
            if as_dict:
                assert len(row) == 3, "Dict mode only supports rows with two values + uid"
                data[row[0]] = row[1]
            else:
                data.append(row[:-1])
                uid.append(row[3])
    return data, uid


def save_tsv(data, path: str, delim: str = "\t", mode="w"):
    with open(path, mode, newline="") as f:
        csvwriter = csv.writer(f, delimiter=delim)
        csvwriter.writerows(data)


def calc_ngram(string, n):
    string = ["".join(string).lower().replace(" ", "")]
    return set([[b[i:i + n] for i in range(len(b) - n + 1)] for b in string][0])


def calc_sims(target, reference, fun):
    sims = np.zeros(len(reference), dtype=np.float32)
    for i, ref in enumerate(reference):
        sims[i] = fun(target, ref)
    return sims


def guess_params(dice, known_set_size, max_set_size=40):
    poss_setsizes = []
    poss_intersects = []
    for guess_set_size in range(max_set_size):
        for guess_intersect in range(min(guess_set_size, known_set_size)):
            if round(2 * (guess_intersect) / (known_set_size + guess_set_size), 1) == round(dice, 1):
                poss_setsizes.append(guess_set_size)
                poss_intersects.append(guess_intersect)
    return set(poss_setsizes)


def dice(a, b):
    return 2 * len(a.intersection(b)) / (len(a) + len(b))


def jaccard(a, b):
    return a.intersection(b) / ((len(a) + len(b)) - len(a.intersection(b)))


def est_bf_elements(bf, k):
    # https://en.wikipedia.org/wiki/Bloom_filter#Approximating_the_number_of_items_in_a_Bloom_filter
    m = len(bf)
    return -(m / k) * math.log(1 - (sum(bf) / m))


def est_bf_union(bf_a, bf_b, k):
    m = len(bf_a)
    return -(m / k) * math.log(1 - (sum(np.logical_or(bf_a, bf_b)) / m))


def pairwise_dice(setlist_a, setlist_b):
    if type(setlist_a) == set:
        setlist_a = [setlist_a]
    if type(setlist_b) == set:
        setlist_b = [setlist_b]
    sims = np.zeros((1, len(setlist_a) * len(setlist_b)), dtype=float)
    i = 0
    for set_a in setlist_a:
        for set_b in setlist_b:
            sims[0][i] = dice(set_a, set_b)
            i += 1
    return sims


def pairwise_jaccard(setlist_a, setlist_b):
    if type(setlist_a) == set:
        setlist_a = [setlist_a]
    if type(setlist_b) == set:
        setlist_b = [setlist_b]
    sims = np.zeros((1, len(setlist_a) * len(setlist_b)), dtype=float)
    i = 0
    for set_a in setlist_a:
        for set_b in setlist_b:
            sims[0][i] = jaccard(set_a, set_b)
            i += 1
    return sims


def est_1bit_jacc(arr_a, arr_b):
    assert arr_a.shape[0] == arr_b.shape[0]
    collisions = sum(arr_a == arr_b)
    return (2 * (collisions / arr_a.shape[0]) - 1)


def est_1bit_dice(arr_a, arr_b):
    jacc = est_1bit_jacc(arr_a, arr_b)
    return (2 * jacc) / (1 + jacc)


def dice_sim(arr_a, arr_b):
    num_common = len(np.intersect1d(arr_a, arr_b))
    total_unique = len(np.unique(arr_a)) + len(np.unique(arr_b))
    return (2.0 * num_common) / (total_unique)


def jacc_sim(arr_a, arr_b):
    size_intersection = len(np.intersect1d(arr_a, arr_b))
    size_union = len(np.union1d(arr_a, arr_b))
    return float(size_intersection / size_union)


def pairwise_jacc_tmh(arrlist_a, arrlist_b, onebit=True):
    if onebit:
        simfunc = est_1bit_jacc
    else:
        simfunc = jacc_sim

    if len(arrlist_a.shape) == 1:
        arrlist_a = arrlist_a.reshape(1, -1)
    if len(arrlist_b.shape) == 1:
        arrlist_b = arrlist_b.reshape(1, -1)
    sims = np.zeros((1, len(arrlist_a) * len(arrlist_b)), dtype=float)
    i = 0
    for arr_a in arrlist_a:
        for arr_b in arrlist_b:
            sims[0][i] = simfunc(arr_a, arr_b)
            i += 1
    return sims


def guess_zero_overlap(target_sims, known_plaintexts, included_ngr, avg_plaintext_length, not_included_ngr=None,
                       ratio=0.3, verbose=False):
    if not_included_ngr is None:
        not_included_ngr = set()
    i = 0
    poss_zero_overlap = []
    for sim, ngr in zip(target_sims, known_plaintexts):
        est_min_dice = 2 / (len(ngr) + avg_plaintext_length)
        if sim <= est_min_dice * ratio and len(included_ngr.intersection(ngr)) == 0:
            poss_zero_overlap.append((i, sim, ngr))
        i += 1

    target_intersect = 0

    for p in poss_zero_overlap:
        not_included_ngr = not_included_ngr.union(p[2])
    return not_included_ngr


def est_bf_intersect(bf_a, bf_b, k):
    return est_bf_elements(bf_a, k) + est_bf_elements(bf_b, k) - est_bf_union(bf_a, bf_b, k)


def buildgraph(available):
    graph = {}
    for a in available:
        if tuple(a[0]) not in graph:
            tmp = set()
        else:
            tmp = graph[tuple(a[0])]
        tmp = tmp.union(a[1])
        graph[tuple(a[0])] = tmp
    return graph


def continuations(graph, n, k, pathsofar):
    if len(pathsofar) >= n:
        graph[tuple(pathsofar[-n])] = graph[tuple(pathsofar[-n])].difference(pathsofar[-(n - 1)])
    if len(pathsofar) == k or pathsofar[-(n - 1):] not in graph or len(graph[pathsofar[-(n - 1):]]) == 0:
        yield pathsofar
    elif len(pathsofar) < k:
        for token in graph[pathsofar[-(n - 1):]]:
            yield from continuations(deepcopy(graph), n, k, pathsofar + (token,))


def allsentences(graph, n, k):
    for ngram in graph:
        yield from continuations(deepcopy(graph), n, k, ngram)


def guess_zero_overlap(target_sims, known_plaintexts, included_ngr=None, not_included_ngr=None, perc=0.5, verbose=False,
                       avglen=1):
    if not_included_ngr is None:
        not_included_ngr = set()

    if included_ngr is None:
        included_ngr = set()

    i = 0
    poss_zero_overlap = []
    poss_included = set()
    pcntl = np.percentile(target_sims, perc)
    # print(min(target_sims) * ratio)
    for jacc, ngr in zip(target_sims, known_plaintexts):
        kp_len = len(ngr)
        #jacc = target_sims[i]
        est_overlap = round((jacc * (kp_len + avglen) / (jacc + 1)))

        if est_overlap <= 0 and len(ngr.intersection(included_ngr)) == 0:
            # if sim <= -0.05 and len(included_ngr.intersection(ngr)) == 0:
            poss_zero_overlap.append((i, jacc, ngr))
        # if sim > max(target_sims)*0.99:
        #    poss_included = poss_included.union(ngr)
        i += 1

    # test = []
    # print(len(poss_zero_overlap))
    for p in poss_zero_overlap:
        not_included_ngr = not_included_ngr.union(p[2])
    return not_included_ngr

def calc_mae_jacc(a, ordered_sim_inds, target_sims, known_plaintexts, overlap_dict, top_n=10):
    jacc_mae = 0
    for i in range(top_n):
        overlap = len(a.intersection(known_plaintexts[ordered_sim_inds[i]]))
        jacc = overlap/((len(a)+len(known_plaintexts[ordered_sim_inds[i]]))-overlap)
        jacc_mae += abs(jacc-target_sims[ordered_sim_inds[i]])
        #jacc_mae += (abs(overlap-overlap_dict[ordered_sim_inds[i]])**2)
    return jacc_mae