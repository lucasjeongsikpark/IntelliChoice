import { useState } from "react";
import type { LocationConsentInterrupt } from "../types";
import type { RespondBody } from "../api/client";

interface Props {
  pending: LocationConsentInterrupt;
  busy: boolean;
  onRespond: (body: Extract<RespondBody, { interrupt_type: "location_consent" }>) => void;
}

// SPEC §5.1.3/§5.22: the notice is shown *before* any location is collected, and the
// location itself (whichever single form the user supplies) is sent only in this one
// approval call - never persisted client-side, never sent through any other request.
export function LocationConsentModal({ pending, busy, onRespond }: Props) {
  const [zipCode, setZipCode] = useState("");
  const [city, setCity] = useState("");
  const [geoError, setGeoError] = useState<string | null>(null);

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
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onRespond({
          interrupt_type: "location_consent",
          approved: true,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      () => setGeoError("Location permission denied - use ZIP or city instead."),
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Find your nearest branch</h2>
        <p className="notice">{pending.notice}</p>

        <button disabled={busy} onClick={shareBrowserLocation}>
          Use my current location
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
        <button disabled={busy || (!zipCode && !city)} onClick={shareTypedLocation}>
          Share location
        </button>

        <button
          className="secondary"
          disabled={busy}
          onClick={() => onRespond({ interrupt_type: "location_consent", approved: false })}
        >
          Don't use my location
        </button>
      </div>
    </div>
  );
}
