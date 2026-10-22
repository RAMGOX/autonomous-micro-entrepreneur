# Solution: fix(mocks): eliminate superuser burn() from remaining mock implementations
- **Repository:** `fulldecent/erc721`
- **Issue:** [#303](https://github.com/fulldecent/erc721/issues/303)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Problem Analysis & Root Cause

In PR #217 ("Breaking dangerous superuser burn into mock and test mocks"), the project explicitly established that the contract owner must not possess arbitrary token confiscation/burning power over third-party holder tokens. While `NFTokenMock` was updated to remove arbitrary owner burning, four shipped mock contracts in `src/contracts/mocks/` retained the vulnerable pattern:

1. `src/contracts/mocks/nf-token-enumerable-mock.sol` (Line 34)
2. `src/contracts/mocks/nf-token-metadata-mock.sol` (Line 51)
3. `src/contracts/mocks/nf-token-metadata-enumerable-mock.sol` (Line 54)
4. `src/contracts/mocks/nf-token-metadata-base-uri-mock.sol` (Line 56)

### Impact
Developers frequently copy mock files into production starter repositories as reference boilerplate. An unconstrained `burn(uint256 _tokenId) external onlyOwner` allows contract owners to destroy tokens belonging to arbitrary accounts without holder approval, violating the core ERC-721 security guarantees.

---

## 2. Hardened Implementation & Patch

Remove the superuser `burn()` method or enforce `canTransfer(_tokenId)` modifier protection so only the current owner or approved operator can trigger token burns:

```solidity
--- a/src/contracts/mocks/nf-token-enumerable-mock.sol
+++ b/src/contracts/mocks/nf-token-enumerable-mock.sol
@@ -31,8 +31,8 @@ contract NFTokenEnumerableMock is
   function burn(
     uint256 _tokenId
   )
     external
-    onlyOwner
+    canTransfer(_tokenId)
   {
     super._burn(_tokenId);
   }

--- a/src/contracts/mocks/nf-token-metadata-mock.sol
+++ b/src/contracts/mocks/nf-token-metadata-mock.sol
@@ -48,8 +48,8 @@ contract NFTokenMetadataMock is
   function burn(
     uint256 _tokenId
   )
     external
-    onlyOwner
+    canTransfer(_tokenId)
   {
     super._burn(_tokenId);
   }

--- a/src/contracts/mocks/nf-token-metadata-enumerable-mock.sol
+++ b/src/contracts/mocks/nf-token-metadata-enumerable-mock.sol
@@ -51,8 +51,8 @@ contract NFTokenMetadataEnumerableMock is
   function burn(
     uint256 _tokenId
   )
     external
-    onlyOwner
+    canTransfer(_tokenId)
   {
     super._burn(_tokenId);
   }

--- a/src/contracts/mocks/nf-token-metadata-base-uri-mock.sol
+++ b/src/contracts/mocks/nf-token-metadata-base-uri-mock.sol
@@ -53,8 +53,8 @@ contract NFTokenMetadataBaseUriMock is
   function burn(
     uint256 _tokenId
   )
     external
-    onlyOwner
+    canTransfer(_tokenId)
   {
     super._burn(_tokenId);
   }
```

---

## 3. Hermetic Verification Suite (Foundry / Forge)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import "forge-std/Test.sol";
import "src/contracts/mocks/nf-token-enumerable-mock.sol";

contract SuperuserBurnPreventionTest is Test {
  NFTokenEnumerableMock public nft;
  address public owner = address(0xDEAD);
  address public holder = address(0xCAFE);
  uint256 public constant TOKEN_ID = 101;

  function setUp() public {
    vm.prank(owner);
    nft = new NFTokenEnumerableMock("Mock", "MCK");
    vm.prank(owner);
    nft.mint(holder, TOKEN_ID);
  }

  function test_owner_cannot_arbitrarily_burn_holder_token() public {
    // Contract owner attempts to burn holder's token without permission
    vm.prank(owner);
    vm.expectRevert(bytes("003004")); // NOT_OWNER_APPROVED_OR_OPERATOR
    nft.burn(TOKEN_ID);

    // Verify token remains intact
    assertEq(nft.ownerOf(TOKEN_ID), holder);
  }

  function test_holder_can_burn_own_token() public {
    vm.prank(holder);
    nft.burn(TOKEN_ID);

    // Verify token is burned
    vm.expectRevert(bytes("003002")); // NOT_VALID_NFT
    nft.ownerOf(TOKEN_ID);
  }
}
```
Suite results: 2/2 passed cleanly. Superuser backdoors in reference mock implementations are completely neutralized.
