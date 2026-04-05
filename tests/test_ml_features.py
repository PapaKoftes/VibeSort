import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml import features as mf


def test_profile_to_feature_vector_base():
    p = {"audio_vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.0], "tags": {}}
    v = mf.profile_to_feature_vector(p)
    assert v.shape == (6,)
    assert v[0] == 0.1


def test_profile_to_feature_vector_with_vocab():
    p = {"audio_vector": [0.5] * 6, "tags": {"sad": 0.8, "night": 0.3}}
    v = mf.profile_to_feature_vector(p, tag_vocab=["sad", "night", "hype"])
    assert v.shape == (9,)
    assert v[6] == 0.8 and v[7] == 0.3 and v[8] == 0.0
