# Code and documentation issues

Static review of `8fbed89`, performed on 2026-11-11. Reviewed the package,
documentation helpers, tests, README, guides, and packaging configuration.
The original review was static; the resolutions below record subsequent fixes
and regression coverage. No physical device validation was performed. Historical
source references describe the reviewed code, before the fixes. Python 3.12's
installed standard-library source was also checked for HTTP exception inheritance
and Base64 decoding behavior.

P1 means a correctness problem to address first. P2 means an error-handling,
API-contract, or documentation-validation problem. P3 means a smaller clarity
or maintenance issue. Finding 10 is conditional on concurrent use and is
separated from defects that also occur with a single caller.

## 1. [P1] Failed verification leaves an unverified token cached

**Status: Resolved.** `authenticate()` keeps the candidate local until verification
succeeds. The failed-verification and successful-verification tests in
[test_client_authentication.py](../tests/test_client_authentication.py) check cache
visibility and a fresh login on the next protected request after failure.

**Source:** [client.py](../tinkly/client.py#L189-L199), token selection at
[client.py](../tinkly/client.py#L346-L352).

`authenticate()` assigns the login token to `self.token` before posting to
`verify`. If verification raises `ProtocolError`, for example after HTTP 500,
invalid JSON, or a socket failure, that token remains installed. Only HTTP 401
clears it. A subsequent protected request sees a non-expired token and skips
authentication, even though verification never completed successfully.

**Direction:** Ensure verification failure cannot leave a token that ordinary
requests treat as authenticated. Keep any in-flight candidate distinct from
successfully verified state, or clear it on failure.

**Coverage needed:** Successful login followed by failed verification; assert
that another protected request does not reuse the unverified token. Existing
client tests do not exercise the login/verify sequence.

## 2. [P1] An already-expired login token recursively starts authentication

**Status: Resolved.** Verification uses the explicit candidate through the shared
private transport, bypassing renewal. Non-positive expiry is rejected, and expiry
during verification raises `AuthenticationError` without caching or retrying.
Expiry tests in [test_client_authentication.py](../tests/test_client_authentication.py)
cover these paths and bound the number of HTTP requests.

**Source:** [client.py](../tinkly/client.py#L179-L198),
[_auth_token](../tinkly/client.py#L346-L352).

An expiry of `0` or a negative integer is accepted and produces an expired
`AuthToken`. The authenticated POST to `verify` calls `_auth_token()`, which
sees the expired candidate and calls `authenticate()` again. If login keeps
returning that expiry, verification is never reached and the client eventually
raises `RecursionError` after repeated login requests. A short positive expiry
can encounter the same control flow if it expires before verification begins.

**Direction:** Verification must use the specific login candidate without
entering ordinary automatic token renewal. Define how an unusable expiry is
reported instead of recursively logging in.

**Coverage needed:** Login responses with zero and negative expiry, and a
candidate expiring between login and verification.

## 3. [P2] HTTP framing failures escape the protocol error boundary

**Status: Resolved.** The transport translates `OSError` and `HTTPException` into
`ProtocolError`, preserving causes and closing connections. The HTTP failure test
in [test_client_authentication.py](../tests/test_client_authentication.py) covers
send failures, `BadStatusLine`, and `IncompleteRead`.

**Source:** [client.py](../tinkly/client.py#L307-L322), documented errors at
[client.py](../tinkly/client.py#L288-L295).

Only `OSError` is converted to `ProtocolError`. `http.client.IncompleteRead`
and `BadStatusLine` instead inherit from `HTTPException`, so a truncated body
or malformed HTTP status line escapes as a standard-library exception. Code
handling the documented `TinklyError`/`ProtocolError` hierarchy misses these
network/protocol failures. The connection still closes; the problem is exception
classification, not connection cleanup.

**Direction:** Translate the HTTP parsing/framing failures that can arise during
sending or reading into `ProtocolError`, preserving their cause. Do not add a
broad `except Exception` handler.

**Coverage needed:** A response read raising `IncompleteRead` and a
`getresponse()` call raising `BadStatusLine`, including connection closure.

## 4. [P2] A malformed expiry string raises an unrelated ValueError

**Status: Resolved.** Invalid integer strings, booleans, unsupported types, and
non-positive expiry raise `AuthenticationError` naming the expiry field. Positive
integer strings and omitted expiry remain supported. Covered by expiry and
successful-login tests in [test_client_authentication.py](../tests/test_client_authentication.py).

**Source:** [client.py](../tinkly/client.py#L179-L187).

The response check accepts every string as numeric, but `int(expires_in)` is
outside any conversion-specific error handling. A value such as `"not-a-number"`
raises bare `ValueError`, whereas an invalid field type raises the more useful
`AuthenticationError`. This happens before the candidate is installed and is
distinct from the renewal recursion in finding 2.

**Direction:** Report failed numeric conversion as an authentication-response
error with the field name. Make the treatment of boolean values explicit too:
`bool` currently passes the `int` check and `False` enters finding 2's zero-expiry
path.

**Coverage needed:** A non-numeric expiry string and boolean expiry values.

## 5. [P2] Routine representations and error messages expose tokens

**Status: Resolved.** Token and challenge-response fields are excluded from repr.
Protocol error messages omit response bodies and untrusted application-code values;
404 errors retain their explicit `.text` attribute without printing it. Credential
tests in [test_client_authentication.py](../tests/test_client_authentication.py)
cover representations and malformed, non-object, application, and HTTP errors.

**Source:** [AuthToken and TwinklyClient](../tinkly/client.py#L63-L97),
[response errors](../tinkly/client.py#L324-L343).

The default dataclass representations include `AuthToken.value`, and representing
an authenticated `TwinklyClient` includes that nested token. Ordinary debug
logging of either object therefore prints the authentication credential.
Separately, malformed JSON errors interpolate the entire raw response body.
A truncated login JSON object containing an authentication token would copy
that token into the exception message. Other response-error paths also include
complete device response bodies.

**Direction:** Exclude credential fields from routine representations and avoid
including credential-bearing login/verification response bodies in error text.
Keep endpoint/status/error context useful without printing secret values.

**Coverage needed:** Use a synthetic token marker and assert that it does not
appear in client/token representations or malformed-login exception messages.

## 6. [P2] Slow discovery consumers lose replies already queued in time

**Status: Resolved by defining the iterator contract.** Discovery remains lazy;
its docstring requires prompt consumption, normally `list(discover())`, for a
complete scan. Consumer work counts toward the fixed deadline. The consumer-delay
test in [test_discovery.py](../tests/test_discovery.py) demonstrates that queued
replies are left unread when the consumer resumes after the deadline.

**Source:** [discovery.py](../tinkly/discovery.py#L71-L86), iterator contract at
[discovery.py](../tinkly/discovery.py#L53-L64).

The first result sets the 100 ms collection deadline and then yields. If the
consumer spends 200 ms inspecting that device before requesting the next result,
the loop exits at its deadline check without draining other replies that arrived
within the collection window. The public iterator can therefore return fewer
devices than `list(discover())` on the same packet arrivals. The documentation
does not explain this dependency on consumer speed.

**Direction:** State that callers wanting the full scan must consume it promptly,
as the existing `list(discover())` examples do. If collection must be independent
of consumer work, decide that API contract before changing the implementation.
The chosen fixed post-response window itself is not being challenged here.

**Coverage needed:** Two replies within the window, with the fake clock advanced
past the deadline by the consumer between `next()` calls.

## 7. [P2] Non-ASCII tokens bypass frame token error handling

**Status: Resolved.** The Base64 conversion catches `ValueError`, including its
`binascii.Error` subclass, only around token decoding. The bad-token test in
[test_frame.py](../tests/test_frame.py) covers ASCII and non-ASCII failures.

**Source:** [frame.py](../tinkly/frame.py#L35-L40), error contract at
[frame.py](../tinkly/frame.py#L30-L32).

`base64.b64decode()` raises `ValueError` for a non-ASCII string before reaching
the Base64 decoder. The handler catches only `binascii.Error`, so an invalid
non-ASCII token escapes as `ValueError` instead of the documented `ProtocolError`
used for other invalid tokens. The current bad-token test covers ASCII input
only.

**Direction:** Normalize this specific Base64 input failure into the same token
protocol error, without catching errors from unrelated frame processing.

**Coverage needed:** A non-ASCII token with an otherwise valid RGB frame.

## 8. [P2] The page checker accepts links that fail when opened from disk

**Status: Resolved.** The checker now lives in
[reccy](https://github.com/rec/reccy/blob/main/reccy/documentation_pages.py).
With `use_directory_urls = false`, it rejects directory and root-relative page
links even when the target exists in the generated site. Regression tests cover
both forms. Directory URLs remain valid for sites configured to use them.

**Source:** [check_docs.py](../scripts/check_docs.py#L26-L40), local browsing
promise in [contributing.md](../doc/contributing.md#L13-L16).

The checker treats a directory link as its `index.html`, and resolves a
root-relative link against the documentation site directory. With `file://`,
the browser instead displays a directory listing for the first case and resolves
`/...` from the filesystem root for the second. Both can be reported as working
even though clicking the link does not open the checked page. Generated links
currently use explicit HTML files, but the checker would miss a regression or
a handwritten link using these forms.

**Direction:** Validate links according to the supported local-file browsing
mode, including rejecting or correcting directory and root-relative page links.

**Coverage needed:** Existing `guide/index.html` with `href="guide/"`, and an
existing site page referenced by a root-relative URL.

## 9. [P2] Invisible script or style text makes a blank page pass

**Status: Resolved.** Reccy's checker excludes script and style text from article
content. Regression tests reject heading-only pages containing either element.
This does not evaluate arbitrary CSS or JavaScript visibility.

**Source:** [check_docs.py](../scripts/check_docs.py#L55-L74).

`handle_data()` counts all non-heading text inside an article as content. It
also receives text inside `script` and `style` elements. An article containing
only a heading and an inline script or stylesheet therefore passes the
non-blank check even though it displays no body content. The existing blank-page
test covers navigation and headings, but not invisible text.

**Direction:** Exclude text from elements that do not render article content.
Keep the guarantee precise: checking article text does not prove that arbitrary
CSS or JavaScript will leave that text visible in a browser.

**Coverage needed:** Heading-only articles containing script text and style text.

## 10. [P2, conditional] Shared-client and shared-controller ownership is unclear

**Status: Resolved by defining caller ownership.** The client docstring requires
serialized use; `send_frame()` requires serialization of whole frames per
controller even across separate sockets. Concurrent use is not supported, so no
locks, concurrent API, or interleaving tests are introduced.

**Source:** [client.py](../tinkly/client.py#L189-L199),
[401 handling](../tinkly/client.py#L299-L325),
[frame.py](../tinkly/frame.py#L74-L79).

The client is described as synchronous, but neither its documentation nor the
frame documentation states a concurrency/ownership contract. If a client is
shared between threads, a delayed HTTP 401 for token A can clear a newer token B
installed by another call: the error path unconditionally assigns `None` without
checking which token was sent. Authentication can also expose its unverified
candidate to another request, and `authenticate()` returns the current shared
field rather than necessarily its own candidate.

Separately, concurrent fragmented sends to the same controller can interleave
packets from different frames. Fragment numbering restarts at zero for every
call, and neither a shared socket nor separate sockets serialize a whole frame.
Keeping input buffers unchanged, as already documented, does not prevent this.

**Direction:** First document single-owner client use and serialization of frame
sends to each controller, if that is the intended API. Add synchronization only
if shared concurrent use is actually required. This is a conditional API-contract
finding, not a claim that the current examples or tests use concurrent callers.

**Coverage needed if concurrency is supported:** Controlled interleavings of
token refresh with a stale 401, and of two multi-fragment frame transmissions.

## 11. [P3] get_network_scan sounds like a read but starts an operation

**Status: Resolved.** `start_network_scan()` is the sole operation name. Its
property documentation, [test_client.py](../tests/test_client.py), and lyte's
networking/diagnostic callers and diagnostic test doubles use the new name.

**Source:** [client.py](../tinkly/client.py#L249-L255).

The implementation and docstring start a scan; reading the results is a separate
property. The `get_` name still suggests retrieval, unlike the action/property
distinction used elsewhere in the API.

**Direction:** Consider `start_network_scan()` as the single canonical operation
name, updating callers and documentation together if the rename is approved.

## 12. [P3] MAC parsing contains an unreachable error branch

**Status: Resolved.** The unreachable handler is removed. Permissive separator
filtering and length validation remain unchanged, covered by the existing MAC
parsing tests in [test_authentication.py](../tests/test_authentication.py).

**Source:** [authentication.py](../tinkly/authentication.py#L18-L24).

The regular expression removes every non-ASCII-hex character, and the length
check then requires exactly twelve remaining hex characters. `bytes.fromhex()`
cannot raise the caught non-hex `ValueError` for that value, so the second
error message describes a check that can never fail there.

**Direction:** Remove the dead handler if permissive filtering is intentional.
If stricter address syntax is desired, define it separately rather than relying
on this unreachable branch. Common colon/hyphen formats are already tested.

## 13. [P3] The API prefix is unnecessarily assembled from three literals

**Status: Resolved.** The prefix is the single literal `'/xled/v1'`. Request-path
assertions in [test_client.py](../tests/test_client.py) and the handshake tests
exercise its use in HTTP requests.

**Source:** [client.py](../tinkly/client.py#L16).

`'/' + 'x' + 'led/v1'` always produces `/xled/v1`, but obscures the endpoint prefix
when scanning the file or searching for the literal path used in documentation.
There is no dynamic value or compatibility behavior involved.

**Direction:** Use the single literal `'/xled/v1'`. This is a readability issue,
not a protocol behavior change.

## Review boundaries

- Automatic retries, extra transport versions, RGBW support, and support for more
  device models are not proposed: the existing documents assign retries and
  coordination to callers and explicitly describe the current RGB/v3 transport.
- The 100 ms discovery window and propagation of malformed discovery replies are
  intentional current decisions, not findings by themselves.
- Lazy frame validation, shared pixel buffers, and partial UDP transmission on
  failure are already documented; they were not counted as new defects.
- No device behavior, network performance, or thread interleaving was measured.
  Automated coverage uses controlled HTTP/socket responses and clocks.
