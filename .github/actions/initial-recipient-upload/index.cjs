'use strict';

// Fixed initial-only terminal route. No admission, helper-path or token input.
// This Action's presence does not activate a workflow or lift a Release HOLD.
require('../../../scripts/hosted-initial-artifact-action.cjs').main();
