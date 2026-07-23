// Attached only to the default (S3 frontend) cache behavior, never the API path
// patterns - rewriting happens before the request reaches origin, so it can't corrupt
// the ALB origin's real JSON error responses the way a distribution-wide
// custom_error_response would (see main.tf's comment on that near-miss).
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Any request whose last path segment has no "." is treated as a client-side route
  // (e.g. /session/abc) and served index.html so the SPA router can take over; a real
  // static asset (main.js, favicon.ico, ...) always has an extension.
  if (!uri.includes(".")) {
    request.uri = "/index.html";
  }

  return request;
}
