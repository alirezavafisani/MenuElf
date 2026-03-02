// app/components/MapView.tsx
import React, { forwardRef } from 'react';
import RNMapView, { MapViewProps, Marker as RNMarker, Callout as RNCallout, PROVIDER_GOOGLE } from 'react-native-maps';

const MapView = forwardRef<RNMapView, MapViewProps>((props, ref) => {
    return <RNMapView ref={ref} provider={PROVIDER_GOOGLE} {...props} />;
});

export const Marker = RNMarker;
export const Callout = RNCallout;
export { PROVIDER_GOOGLE };
export default MapView;
