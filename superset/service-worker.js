addEventListener('fetch', function(event) {
    console.log('fetch');
    console.log(event);
    // Can override response if we would like
    //event.respondWith(fetch(event.request.url));
});
