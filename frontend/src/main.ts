import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@fontsource-variable/bricolage-grotesque/index.css'
import '@fontsource-variable/hanken-grotesk/index.css'
import '@fontsource/space-mono/400.css'
import '@fontsource/space-mono/700.css'
import './style.css'
import App from './App.vue'
import { router } from './router'
import { bindSocketToStores } from './socket/bindStores'
import { connect } from './socket/client'

const app = createApp(App)
app.use(createPinia())
app.use(router)

bindSocketToStores() // wire socket → stores before the first connect fires
connect()

app.mount('#app')