/**
 * Setup for the `dom` vitest project (see vite.config.ts). Not a test file and not part of
 * the app bundle — nothing in src/main.tsx imports it.
 */

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// @testing-library/react only auto-registers this when vitest globals are enabled, and they
// are not. Registering it here is what keeps renders from leaking between tests.
afterEach(cleanup)
