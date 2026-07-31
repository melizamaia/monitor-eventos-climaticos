import { Component } from '@angular/core';
import { MapaEventosComponent } from './mapa-eventos/mapa-eventos.component';

@Component({
  selector: 'app-root',
  imports: [MapaEventosComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {}
