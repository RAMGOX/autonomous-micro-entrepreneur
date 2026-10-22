# Solution: zones: add a thank-you page that serves the download after Polar checkout
- **Issue:** [Givdul/zones-web #12](https://github.com/Givdul/zones-web/issues/12)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
Polar checkout redirects customers to `https://apps.givdul.com/zones?checkout_id={CHECKOUT_ID}`. Because the site is a static Astro build without a server adapter or query parameter listener, visitors are shown the plain landing page with no download triggered.

### Implementation Patch

```astro
---
// diff --git a/src/pages/thank-you.astro b/src/pages/thank-you.astro
// new file mode 100644
import Layout from '../layouts/Layout.astro';
---

<Layout title="Thank You for Downloading Zones">
  <main class="max-w-2xl mx-auto px-4 py-16 text-center">
    <div id="loading-state" class="space-y-4">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
      <h1 class="text-2xl font-bold">Verifying your download...</h1>
      <p class="text-gray-600">Please wait while we prepare your Zones license and binary.</p>
    </div>

    <div id="success-state" class="hidden space-y-6">
      <div class="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto text-3xl">✔</div>
      <h1 class="text-3xl font-bold text-gray-900">Thank You for Getting Zones!</h1>
      <p class="text-gray-600">Your download should begin automatically. If it doesn't, click below:</p>
      <div class="pt-2">
        <a id="download-button" href="#" class="inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-3 rounded-lg shadow transition">
          Download Zones (.dmg / .zip)
        </a>
      </div>
    </div>
  </main>

  <script>
    async function handleCheckoutConfirmation() {
      const params = new URLSearchParams(window.location.search);
      const checkoutId = params.get('checkout_id');

      if (!checkoutId) {
        window.location.href = '/zones';
        return;
      }

      try {
        // Query Polar client checkout session
        const res = await fetch(`https://api.polar.sh/v1/checkouts/client/${checkoutId}`);
        const data = await res.json();

        // Extract download link from benefit grants or product attachment
        const downloadUrl = data.product?.file_url || data.customer_session?.customer_portal_url;

        document.getElementById('loading-state')?.classList.add('hidden');
        document.getElementById('success-state')?.classList.remove('hidden');

        if (downloadUrl) {
          const btn = document.getElementById('download-button') as HTMLAnchorElement;
          btn.href = downloadUrl;
          // Trigger instant download
          window.location.href = downloadUrl;
        }
      } catch (err) {
        console.error('Failed to verify Polar checkout:', err);
      }
    }

    handleCheckoutConfirmation();
  </script>
</Layout>
```

```javascript
// diff --git a/scripts/setup-polar-zones.mjs b/scripts/setup-polar-zones.mjs
// Update success_url target
- success_url: 'https://apps.givdul.com/zones?checkout_id={CHECKOUT_ID}',
+ success_url: 'https://apps.givdul.com/thank-you?checkout_id={CHECKOUT_ID}',
```
