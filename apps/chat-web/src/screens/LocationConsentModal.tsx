import { useState } from "react";
import { ApprovalModal } from "../components/ApprovalModal";
import type { LocationConsentInterrupt } from "../types";
import type { RespondBody } from "../api/client";

interface Props {
  pending: LocationConsentInterrupt;
  busy: boolean;
  error?: string | null;
  onRespond: (body: Extract<RespondBody, { interrupt_type: "location_consent" }>) => void;
}

// SPEC §5.1.3/§5.22: the notice is shown *before* any location is collected, and the
// location itself (whichever single form the user supplies) is sent only in this one
// approval call - never persisted client-side, never sent through any other request.
export function LocationConsentModal({ pending, busy, error, onRespond }: Props) {
  const [zipCode, setZipCode] = useState("");
  const [city, setCity] = useState("");
  const [geoError, setGeoError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  function shareTypedLocation() {
    onRespond({
      interrupt_type: "location_consent",
      approved: true,
      zip_code: zipCode || null,
      city: city || null,
    });
  }

  function shareBrowserLocation() {
    setGeoError(null);
    if (!("geolocation" in navigator)) {
      setGeoError("This browser doesn't support location sharing - use ZIP or city instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        onRespond({
          interrupt_type: "location_consent",
          approved: true,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        setLocating(false);
        // D-352: distinguished, because "you said no" and "your device never answered" call
        // for different next steps. `TIMEOUT` is `code === 3`.
        setGeoError(
          error.code === error.TIMEOUT
            ? "Finding your location took too long - use ZIP or city instead."
            : "Location permission denied - use ZIP or city instead.",
        );
      },
      // D-352: `getCurrentPosition` had no options at all, so a permission prompt left open
      // or an OS that never returns a fix left the dialog sitting there with every button
      // enabled and nothing happening - no spinner, no eventual error, no way to tell it
      // apart from a dead app. 15s is generous for a real fix; `maximumAge` accepts a recent
      // cached position rather than insisting on a fresh satellite read for "which branch is
      // near me".
      { timeout: 15_000, maximumAge: 300_000 },
    );
  }

  const decline = () =>
    onRespond({ interrupt_type: "location_consent", approved: false });

  return (
    // Escape withholds the location, which is the only safe reading of "get me out of here"
    // on a consent dialog (D-219).
    <ApprovalModal titleId="location-consent-title" error={error} onDismiss={decline}>
      <h2 id="location-consent-title">Find your nearest branch</h2>
      <p className="notice">{pending.notice}</p>

      <button disabled={busy || locating} onClick={shareBrowserLocation}>
        {locating ? "Finding you…" : "Use my current location"}
      </button>
      {geoError && <p className="error">{geoError}</p>}

      <label className="field">
        <span>ZIP code</span>
        <input value={zipCode} onChange={(e) => setZipCode(e.target.value)} />
      </label>
      <label className="field">
        <span>or city</span>
        <input value={city} onChange={(e) => setCity(e.target.value)} />
      </label>
      <button disabled={busy || locating || (!zipCode && !city)} onClick={shareTypedLocation}>
        Share location
      </button>

      <button className="secondary" disabled={busy} onClick={decline}>
        Don't use my location
      </button>
    </ApprovalModal>
  );
}
