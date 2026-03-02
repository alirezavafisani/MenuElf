// app/components/MapView.web.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function MapView(props: any) {
    return (
        <View style={[styles.container, props.style]}>
            <Text style={styles.text}>Map View is not fully supported on Web.</Text>
            <Text style={styles.subText}>Please use the iOS/Android app or scan the QR code to use the interactive map.</Text>
        </View>
    );
}

export const Marker = ({ children }: any) => <>{children}</>;
export const Callout = ({ children }: any) => <>{children}</>;
export const PROVIDER_GOOGLE = "google";

const styles = StyleSheet.create({
    container: {
        backgroundColor: '#E8E0D8',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 24,
    },
    text: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1A1A1A',
        textAlign: 'center',
        marginBottom: 8,
    },
    subText: {
        fontSize: 14,
        color: '#7A7A7A',
        textAlign: 'center',
    }
});
