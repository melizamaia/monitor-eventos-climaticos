import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface EventoProperties {
  id: string;
  fonte: string;
  tipo: string;
  severidade: string;
  municipio: string;
  estado: string;
  data_ocorrencia: string;
  descricao: string;
  url: string;
}

export interface EventoFeature {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
  properties: EventoProperties;
}

export interface EventosFeatureCollection {
  type: 'FeatureCollection';
  features: EventoFeature[];
}

const API_URL = 'http://localhost:8000/eventos';

@Injectable({ providedIn: 'root' })
export class EventosService {
  constructor(private readonly http: HttpClient) {}

  listar(): Observable<EventosFeatureCollection> {
    return this.http.get<EventosFeatureCollection>(API_URL);
  }
}
