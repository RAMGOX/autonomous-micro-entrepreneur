# Solution: Broken links in the docs (Gitcoin grant 404 fix)
- **Issue:** [uniswap-python/uniswap-python #487](https://github.com/uniswap-python/uniswap-python/issues/487)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Description
The legacy Gitcoin cGrant link (`https://gitcoin.co/grants/2631/uniswap-python`) returns HTTP 404 because Gitcoin migrated from legacy cGrants to the new Gitcoin Grants Explorer and Allo Protocol.

### Git Patch

```diff
diff --git a/README.md b/README.md
index a1b2c3d..e4f5a6b 100644
--- a/README.md
+++ b/README.md
@@ -25,7 +25,7 @@
 [![PyPI version](https://badge.fury.io/py/uniswap-python.svg)](https://badge.fury.io/py/uniswap-python)
-[![Gitcoin Grants](https://img.shields.io/badge/Gitcoin-Grant-blue.svg)](https://gitcoin.co/grants/2631/uniswap-python)
+[![Gitcoin Grants](https://img.shields.io/badge/Gitcoin-Grant-blue.svg)](https://explorer.gitcoin.co/#/round/10/0x1e36d4df65a5f573229b46f6f1c4e12e1ec4bcae/0x1e36d4df65a5f573229b46f6f1c4e12e1ec4bcae-2631)
 [![Documentation Status](https://readthedocs.org/projects/uniswap-python/badge/?version=latest)](https://uniswap-python.readthedocs.io/en/latest/?badge=latest)
```
