import { StyleSheet, View, Text, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';

export default function FriendsScreen() {
    const handleLogout = () => {
        Alert.alert('Log Out', 'Are you sure you want to log out?', [
            { text: 'Cancel', style: 'cancel' },
            {
                text: 'Log Out',
                style: 'destructive',
                onPress: () => supabase.auth.signOut(),
            },
        ]);
    };

    return (
        <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
            <View style={styles.centerBox}>
                <Text style={styles.emoji}>👥</Text>
                <Text style={styles.title}>Group Dining</Text>
                <Text style={styles.subtitle}>Coming Soon!</Text>
            </View>
            <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
                <Text style={styles.logoutText}>Log Out</Text>
            </TouchableOpacity>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FBF7F4',
    },
    centerBox: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 40,
        backgroundColor: '#FFFFFF',
        margin: 24,
        borderRadius: 24,
        borderWidth: 1,
        borderColor: '#E8E0D8',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.05,
        shadowRadius: 20,
        elevation: 5,
    },
    emoji: {
        fontSize: 64,
        marginBottom: 20,
    },
    title: {
        fontSize: 24,
        fontWeight: '800',
        color: '#1A1A1A',
        marginBottom: 12,
        textAlign: 'center',
    },
    subtitle: {
        fontSize: 16,
        color: '#7A7A7A',
        textAlign: 'center',
        lineHeight: 24,
    },
    logoutBtn: {
        marginHorizontal: 24,
        marginBottom: 24,
        paddingVertical: 14,
        borderRadius: 14,
        borderWidth: 1,
        borderColor: '#E8E0D8',
        backgroundColor: '#FFFFFF',
        alignItems: 'center',
    },
    logoutText: {
        color: '#E74C3C',
        fontSize: 16,
        fontWeight: '600',
    },
});
