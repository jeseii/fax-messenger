// static/service-worker.js
const CACHE_NAME = 'fax-messenger-v1';
const STATIC_ASSETS = [
    '/',
    '/static/default-avatar.png',
    '/static/group-icon.png'
];

// Установка service worker
self.addEventListener('install', event => {
    console.log('Service Worker installed');
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Активация
self.addEventListener('activate', event => {
    console.log('Service Worker activated');
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// Обработка push-уведомлений
self.addEventListener('push', event => {
    console.log('Push received:', event);
    
    let data = {};
    try {
        data = event.data.json();
    } catch (e) {
        data = {
            title: 'FAX Messenger',
            body: event.data ? event.data.text() : 'New notification',
            vibrate: [200, 100, 200, 100, 200, 100, 200],
            requireInteraction: true
        };
    }
    
    const title = data.title || 'FAX Messenger';
    const options = {
        body: data.body || 'You have a new message',
        icon: data.icon || '/static/fax-icon-192.png',
        badge: '/static/fax-icon-96.png',
        vibrate: data.vibrate || [200, 100, 200, 100, 200, 100, 200], // Паттерн вибрации
        sound: data.sound || '/static/notification.mp3', // Звук уведомления
        requireInteraction: data.requireInteraction !== false, // Остается до взаимодействия
        tag: data.tag || 'message',
        renotify: true,
        data: {
            url: data.url || '/',
            chatId: data.chatId,
            messageId: data.messageId,
            callId: data.callId,
            callType: data.callType,
            timestamp: Date.now()
        },
        actions: data.actions || [
            { action: 'open', title: 'Open' },
            { action: 'close', title: 'Dismiss' }
        ]
    };
    
    // Для звонков - особое уведомление
    if (data.callType) {
        options.vibrate = [500, 200, 500, 200, 500, 200, 1000]; // Более длинная вибрация для звонка
        options.requireInteraction = true;
        options.actions = [
            { action: 'answer', title: 'Answer' },
            { action: 'decline', title: 'Decline' },
            { action: 'open', title: 'Open App' }
        ];
    }
    
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', event => {
    console.log('Notification clicked:', event);
    event.notification.close();
    
    const notificationData = event.notification.data;
    const action = event.action;
    
    // Обработка действий для звонков
    if (notificationData.callType) {
        if (action === 'answer') {
            // Открываем приложение и принимаем звонок
            event.waitUntil(
                clients.matchAll({ type: 'window', includeUncontrolled: true })
                    .then(windowClients => {
                        for (let client of windowClients) {
                            if (client.url.includes('/') && 'focus' in client) {
                                client.focus();
                                client.postMessage({
                                    type: 'ANSWER_CALL',
                                    callId: notificationData.callId,
                                    callType: notificationData.callType,
                                    fromUserId: notificationData.fromUserId
                                });
                                return;
                            }
                        }
                        if (clients.openWindow) {
                            return clients.openWindow('/?answer_call=' + notificationData.callId);
                        }
                    })
            );
            return;
        } else if (action === 'decline') {
            // Отправляем событие об отклонении звонка
            event.waitUntil(
                clients.matchAll({ type: 'window', includeUncontrolled: true })
                    .then(windowClients => {
                        for (let client of windowClients) {
                            client.postMessage({
                                type: 'DECLINE_CALL',
                                callId: notificationData.callId
                            });
                        }
                    })
            );
            return;
        }
    }
    
    // Обычное открытие для сообщений
    if (action === 'open' || !action) {
        event.waitUntil(
            clients.matchAll({ type: 'window', includeUncontrolled: true })
                .then(windowClients => {
                    for (let client of windowClients) {
                        if (client.url.includes('/') && 'focus' in client) {
                            client.focus();
                            if (notificationData.chatId) {
                                client.postMessage({
                                    type: 'OPEN_CHAT',
                                    chatId: notificationData.chatId,
                                    messageId: notificationData.messageId
                                });
                            }
                            return;
                        }
                    }
                    if (clients.openWindow) {
                        let url = '/';
                        if (notificationData.chatId) {
                            url += '?chat=' + notificationData.chatId;
                        }
                        return clients.openWindow(url);
                    }
                })
        );
    }
});

// Fetch с кэшированием
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});