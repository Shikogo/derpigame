import { createApp } from 'vue'
import { createPinia } from 'pinia'

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